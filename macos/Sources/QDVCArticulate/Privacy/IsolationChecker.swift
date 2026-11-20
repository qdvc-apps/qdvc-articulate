import Foundation
import Security
import Darwin

/// Verifies — at runtime, from inside the app — that macOS is enforcing network isolation.
struct IsolationReport: Equatable {
    enum Probe: Equatable {
        case blocked(String)
        case notBlocked(String)

        var isBlocked: Bool {
            if case .blocked = self { return true }
            return false
        }

        var detail: String {
            switch self {
            case .blocked(let s), .notBlocked(let s): return s
            }
        }
    }

    var sandboxed: Bool
    var networkClientEntitlement: Bool
    var networkServerEntitlement: Bool
    var probe: Probe?

    /// True when the OS guarantees the app cannot open network connections.
    var isIsolated: Bool {
        sandboxed && !networkClientEntitlement && !networkServerEntitlement && (probe?.isBlocked ?? true)
    }
}

enum IsolationChecker {
    /// Reads this process's own code-signing entitlements. No I/O, no network.
    static func staticReport() -> IsolationReport {
        IsolationReport(
            sandboxed: entitlement("com.apple.security.app-sandbox")
                || ProcessInfo.processInfo.environment["APP_SANDBOX_CONTAINER_ID"] != nil,
            networkClientEntitlement: entitlement("com.apple.security.network.client"),
            networkServerEntitlement: entitlement("com.apple.security.network.server"),
            probe: nil
        )
    }

    /// Full report including a live probe.
    static func fullReport() -> IsolationReport {
        var report = staticReport()
        report.probe = probeLoopback()
        return report
    }

    private static func entitlement(_ key: String) -> Bool {
        guard let task = SecTaskCreateFromSelf(nil) else { return false }
        let value = SecTaskCopyValueForEntitlement(task, key as CFString, nil)
        return (value as? Bool) ?? false
    }

    /// Tries to open a TCP connection to 127.0.0.1 (the machine itself — even if this were allowed,
    /// nothing would leave the device). Inside the App Sandbox without a network entitlement the
    /// kernel refuses the attempt with EPERM, which proves isolation is enforced by macOS itself.
    static func probeLoopback() -> IsolationReport.Probe {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        if fd < 0 {
            return .blocked("Creating a network socket was refused (\(errorString(errno))).")
        }
        defer { close(fd) }
        _ = fcntl(fd, F_SETFL, O_NONBLOCK)

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = in_port_t(9).bigEndian
        address.sin_addr.s_addr = inet_addr("127.0.0.1")

        let result = withUnsafePointer(to: address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { socketAddress in
                connect(fd, socketAddress, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        let code = errno
        if result == 0 {
            return .notBlocked("A loopback connection succeeded.")
        }
        switch code {
        case EPERM, EACCES:
            return .blocked("The connection attempt was denied by macOS (\(errorString(code))).")
        default:
            return .notBlocked("The operating system allowed a connection attempt (\(errorString(code))).")
        }
    }

    private static func errorString(_ code: Int32) -> String {
        String(cString: strerror(code))
    }
}
