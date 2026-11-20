/*
 * The fixed interface between the Python app (qdvc/llm.py, through ctypes)
 * and llama.cpp. Plain C types only, so it does not change when llama.cpp's
 * structs do. Bump QAL_API_VERSION when this file changes; llm.py refuses a
 * library with another version.
 */
#ifndef ARTICULATE_LLAMA_H
#define ARTICULATE_LLAMA_H

#ifdef __cplusplus
extern "C" {
#endif

#define QAL_API_VERSION 1

#define QAL_OK 0
#define QAL_CANCELLED 1
#define QAL_ERR_NO_MODEL (-1)
#define QAL_ERR_TOKENIZE (-2)
#define QAL_ERR_TOO_LONG (-3)
#define QAL_ERR_DECODE (-4)
#define QAL_ERR_GRAMMAR (-5)

typedef struct qal_engine qal_engine;

int qal_api_version(void);
const char *qal_system_info(void);

/* n_threads <= 0: the number of CPUs less two. On failure: NULL, with a message in err. */
qal_engine *qal_load(const char *path, int n_ctx, int n_gpu_layers, int n_threads, int n_batch,
                     char *err, int errlen);
void qal_free(qal_engine *engine);

/* what: "desc", "arch", "name" or "template". Returns the length, or -1 when absent. */
int qal_meta(qal_engine *engine, const char *what, char *buf, int buflen);
unsigned long long qal_size(qal_engine *engine);
unsigned long long qal_n_params(qal_engine *engine);
int qal_n_ctx_train(qal_engine *engine);
int qal_n_ctx(qal_engine *engine);

/* Generates a reply to prefix + body. The prefix (the instructions) is kept in the KV cache and
 * reused while it is unchanged (reuse_prefix). grammar: GBNF, or NULL. cancel: polled before each
 * token; set it to 1 from another thread to stop. On QAL_OK, *out holds the UTF-8 reply, to be
 * released with qal_free_string. Not thread-safe: one generation per engine at a time. */
int qal_generate(qal_engine *engine, const char *prefix, const char *body, const char *grammar,
                 int max_tokens, float temperature, int reuse_prefix, unsigned int seed,
                 volatile int *cancel, char **out, char *err, int errlen);
void qal_free_string(char *s);

#ifdef __cplusplus
}
#endif

#endif
