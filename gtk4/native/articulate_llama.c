/*
 * libqdvc-articulate-llama: the only code in the GTK edition that calls the
 * llama.cpp C API (the counterpart of the macOS edition's LlamaEngine.swift).
 *
 * Python reaches llama.cpp through ctypes, and ctypes needs exact struct
 * layouts, which change between llama.cpp releases. So this small library is
 * compiled against the llama.h of the llama.cpp you placed in vendor/, and
 * offers Python a fixed interface of plain C types (articulate_llama.h).
 * When a llama.cpp update renames something, this file is where the
 * compiler says so.
 *
 * Privacy: llama.cpp is used purely as a local library. Nothing here opens a
 * file other than the model the user chose, and the Flatpak has no network.
 */

#include "articulate_llama.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "llama.h"

struct qal_engine {
    struct llama_model *model;
    struct llama_context *ctx;
    const struct llama_vocab *vocab;
    int n_batch;
    /* Tokens of the prompt prefix currently held in the KV cache (sequence 0). */
    llama_token *cached_prefix;
    int cached_prefix_len;
};

/* --- logging: quiet, but keep the last errors for messages ----------------------------- */

static char last_log[1024];

static void log_callback(enum ggml_log_level level, const char *text, void *user_data) {
    (void) user_data;
    if (level != GGML_LOG_LEVEL_ERROR || text == NULL) {
        return;
    }
    size_t used = strlen(last_log);
    size_t room = sizeof(last_log) - 1 - used;
    if (room < strlen(text)) {
        used = 0; /* start again rather than truncate the newest message */
        room = sizeof(last_log) - 1;
    }
    strncpy(last_log + used, text, room);
    last_log[sizeof(last_log) - 1] = '\0';
}

static void set_error(char *err, int errlen, const char *message) {
    if (err == NULL || errlen <= 0) {
        return;
    }
    char detail[sizeof(last_log)];
    snprintf(detail, sizeof(detail), "%s", last_log);
    size_t n = strlen(detail);
    while (n > 0 && (detail[n - 1] == '\n' || detail[n - 1] == ' ')) {
        detail[--n] = '\0';
    }
    if (n > 0) {
        snprintf(err, (size_t) errlen, "%s (%s)", message, detail);
    } else {
        snprintf(err, (size_t) errlen, "%s", message);
    }
}

static int backend_ready = 0;

static void init_backend(void) {
    if (!backend_ready) {
        llama_log_set(log_callback, NULL);
        llama_backend_init();
        backend_ready = 1;
    }
}

int qal_api_version(void) {
    return QAL_API_VERSION;
}

const char *qal_system_info(void) {
    init_backend();
    return llama_print_system_info();
}

/* --- loading -------------------------------------------------------------------------------- */

qal_engine *qal_load(const char *path, int n_ctx, int n_gpu_layers, int n_threads, int n_batch,
                     char *err, int errlen) {
    init_backend();
    last_log[0] = '\0';

    struct llama_model_params mparams = llama_model_default_params();
    mparams.n_gpu_layers = n_gpu_layers;
    /* The default memory-maps the GGUF (and falls back to a normal read). */

    struct llama_model *model = llama_model_load_from_file(path, mparams);
    if (model == NULL) {
        set_error(err, errlen, "Make sure it is a GGUF model that this build of llama.cpp supports");
        return NULL;
    }

    if (n_threads <= 0) {
        long cpus = sysconf(_SC_NPROCESSORS_ONLN);
        n_threads = cpus > 3 ? (int) cpus - 2 : 1;
    }
    if (n_batch <= 0) {
        n_batch = 1024;
    }

    struct llama_context_params cparams = llama_context_default_params();
    cparams.n_ctx = (uint32_t) n_ctx;
    cparams.n_batch = (uint32_t) n_batch;
    cparams.n_ubatch = (uint32_t) (n_batch < 512 ? n_batch : 512);
    cparams.n_threads = n_threads;
    cparams.n_threads_batch = n_threads;
    /* Keep the full sliding-window cache so the reusable prompt prefix stays valid (Gemma etc.). */
    cparams.swa_full = true;

    struct llama_context *ctx = llama_init_from_model(model, cparams);
    if (ctx == NULL) {
        llama_model_free(model);
        set_error(err, errlen, "Could not create an inference context. Try a smaller context length");
        return NULL;
    }

    qal_engine *e = calloc(1, sizeof(qal_engine));
    if (e == NULL) {
        llama_free(ctx);
        llama_model_free(model);
        set_error(err, errlen, "Out of memory");
        return NULL;
    }
    e->model = model;
    e->ctx = ctx;
    e->vocab = llama_model_get_vocab(model);
    e->n_batch = n_batch;
    return e;
}

void qal_free(qal_engine *e) {
    if (e == NULL) {
        return;
    }
    free(e->cached_prefix);
    llama_free(e->ctx);
    llama_model_free(e->model);
    free(e);
}

int qal_meta(qal_engine *e, const char *what, char *buf, int buflen) {
    if (e == NULL || buf == NULL || buflen <= 0) {
        return -1;
    }
    buf[0] = '\0';
    if (strcmp(what, "desc") == 0) {
        return llama_model_desc(e->model, buf, (size_t) buflen);
    }
    if (strcmp(what, "arch") == 0) {
        return llama_model_meta_val_str(e->model, "general.architecture", buf, (size_t) buflen);
    }
    if (strcmp(what, "name") == 0) {
        return llama_model_meta_val_str(e->model, "general.name", buf, (size_t) buflen);
    }
    if (strcmp(what, "template") == 0) {
        const char *t = llama_model_chat_template(e->model, NULL);
        if (t == NULL) {
            return -1;
        }
        snprintf(buf, (size_t) buflen, "%s", t);
        return (int) strlen(t);
    }
    return -1;
}

unsigned long long qal_size(qal_engine *e) { return e ? llama_model_size(e->model) : 0; }
unsigned long long qal_n_params(qal_engine *e) { return e ? llama_model_n_params(e->model) : 0; }
int qal_n_ctx_train(qal_engine *e) { return e ? llama_model_n_ctx_train(e->model) : 0; }
int qal_n_ctx(qal_engine *e) { return e ? (int) llama_n_ctx(e->ctx) : 0; }

/* --- generating ------------------------------------------------------------------------------- */

static int tokenize(qal_engine *e, const char *text, int add_special, llama_token **out) {
    int len = (int) strlen(text);
    int cap = len + 16;
    llama_token *tokens = malloc(sizeof(llama_token) * (size_t) cap);
    if (tokens == NULL) {
        return -1;
    }
    int n = llama_tokenize(e->vocab, text, len, tokens, cap, add_special != 0, true);
    if (n < 0) {
        cap = -n;
        llama_token *bigger = realloc(tokens, sizeof(llama_token) * (size_t) cap);
        if (bigger == NULL) {
            free(tokens);
            return -1;
        }
        tokens = bigger;
        n = llama_tokenize(e->vocab, text, len, tokens, cap, add_special != 0, true);
    }
    if (n < 0) {
        free(tokens);
        return -1;
    }
    *out = tokens;
    return n;
}

static int decode_all(qal_engine *e, llama_token *tokens, int count) {
    for (int start = 0; start < count; start += e->n_batch) {
        int n = count - start < e->n_batch ? count - start : e->n_batch;
        int rc = llama_decode(e->ctx, llama_batch_get_one(tokens + start, n));
        if (rc != 0) {
            return rc;
        }
    }
    return 0;
}

static void forget_prefix(qal_engine *e) {
    free(e->cached_prefix);
    e->cached_prefix = NULL;
    e->cached_prefix_len = 0;
}

int qal_generate(qal_engine *e, const char *prefix, const char *body, const char *grammar, int max_tokens,
                 float temperature, int reuse_prefix, unsigned int seed, volatile int *cancel,
                 char **out, char *err, int errlen) {
    if (out != NULL) {
        *out = NULL;
    }
    if (e == NULL) {
        set_error(err, errlen, "No model is loaded");
        return QAL_ERR_NO_MODEL;
    }
    last_log[0] = '\0';

    llama_token *prefix_tokens = NULL, *body_tokens = NULL;
    int n_prefix = tokenize(e, prefix, 1, &prefix_tokens);
    int n_body = n_prefix < 0 ? -1 : tokenize(e, body, 0, &body_tokens);
    if (n_prefix < 0 || n_body < 0) {
        free(prefix_tokens);
        free(body_tokens);
        set_error(err, errlen, "Tokenisation failed");
        return QAL_ERR_TOKENIZE;
    }

    int limit = (int) llama_n_ctx(e->ctx);
    if (n_prefix + n_body + max_tokens > limit) {
        char message[256];
        snprintf(message, sizeof(message),
                 "A paragraph is too long for the context window (%d tokens, limit %d). "
                 "Increase the context length or reduce the chunk size",
                 n_prefix + n_body, limit - max_tokens);
        set_error(err, errlen, message);
        free(prefix_tokens);
        free(body_tokens);
        return QAL_ERR_TOO_LONG;
    }

    /* Reuse the KV cache for the (identical) instruction prefix when possible. */
    llama_memory_t memory = llama_get_memory(e->ctx);
    int reused = 0;
    if (reuse_prefix && e->cached_prefix_len == n_prefix && n_prefix > 0
        && memcmp(e->cached_prefix, prefix_tokens, sizeof(llama_token) * (size_t) n_prefix) == 0) {
        reused = llama_memory_seq_rm(memory, 0, n_prefix, -1) ? 1 : 0;
    }
    int rc;
    if (!reused) {
        llama_memory_clear(memory, true);
        forget_prefix(e);
        rc = decode_all(e, prefix_tokens, n_prefix);
        if (rc != 0) {
            free(prefix_tokens);
            free(body_tokens);
            set_error(err, errlen, "The model failed while processing the instructions (llama_decode)");
            return QAL_ERR_DECODE;
        }
        e->cached_prefix = prefix_tokens;
        e->cached_prefix_len = n_prefix;
        prefix_tokens = NULL;
    }
    free(prefix_tokens);

    rc = decode_all(e, body_tokens, n_body);
    free(body_tokens);
    if (rc != 0) {
        forget_prefix(e);
        set_error(err, errlen, "The model failed while processing the text (llama_decode)");
        return QAL_ERR_DECODE;
    }

    /* Sampler chain: grammar constraint first, then greedy or temperature sampling. */
    struct llama_sampler *chain = llama_sampler_chain_init(llama_sampler_chain_default_params());
    if (grammar != NULL && grammar[0] != '\0') {
        struct llama_sampler *g = llama_sampler_init_grammar(e->vocab, grammar, "root");
        if (g == NULL) {
            llama_sampler_free(chain);
            forget_prefix(e);
            set_error(err, errlen, "The output grammar could not be initialised");
            return QAL_ERR_GRAMMAR;
        }
        llama_sampler_chain_add(chain, g);
    }
    if (temperature <= 0.001f) {
        llama_sampler_chain_add(chain, llama_sampler_init_greedy());
    } else {
        llama_sampler_chain_add(chain, llama_sampler_init_top_k(40));
        llama_sampler_chain_add(chain, llama_sampler_init_top_p(0.95f, 1));
        llama_sampler_chain_add(chain, llama_sampler_init_temp(temperature));
        llama_sampler_chain_add(chain, llama_sampler_init_dist(seed));
    }

    size_t cap = 4096, used = 0;
    char *text = malloc(cap);
    if (text == NULL) {
        llama_sampler_free(chain);
        forget_prefix(e);
        set_error(err, errlen, "Out of memory");
        return QAL_ERR_DECODE;
    }
    text[0] = '\0';
    int status = QAL_OK;
    for (int generated = 0; generated < max_tokens; generated++) {
        if (cancel != NULL && *cancel) {
            status = QAL_CANCELLED;
            break;
        }
        llama_token token = llama_sampler_sample(chain, e->ctx, -1);
        if (llama_vocab_is_eog(e->vocab, token)) {
            break;
        }
        char piece[256];
        int n = llama_token_to_piece(e->vocab, token, piece, (int32_t) sizeof(piece), 0, false);
        if (n > 0) {
            if (used + (size_t) n + 1 > cap) {
                while (used + (size_t) n + 1 > cap) {
                    cap *= 2;
                }
                char *bigger = realloc(text, cap);
                if (bigger == NULL) {
                    status = QAL_ERR_DECODE;
                    set_error(err, errlen, "Out of memory");
                    break;
                }
                text = bigger;
            }
            memcpy(text + used, piece, (size_t) n);
            used += (size_t) n;
            text[used] = '\0';
        }
        llama_token next = token;
        if (llama_decode(e->ctx, llama_batch_get_one(&next, 1)) != 0) {
            status = QAL_ERR_DECODE;
            set_error(err, errlen, "The model failed while generating (llama_decode)");
            break;
        }
    }
    llama_sampler_free(chain);
    if (status != QAL_OK) {
        /* The cache now holds a partial answer: start from scratch next time. */
        forget_prefix(e);
        free(text);
        return status;
    }
    if (out != NULL) {
        *out = text;
    } else {
        free(text);
    }
    return QAL_OK;
}

void qal_free_string(char *s) {
    free(s);
}
