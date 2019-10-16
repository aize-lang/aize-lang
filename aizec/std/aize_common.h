#ifndef AIZE_COMMON_H
#define AIZE_COMMON_H
#include "stdint.h"


extern uint32_t aize_mem_depth;


typedef struct AizeBase {
    void* vtable;
    uint32_t depth;
    size_t ref_count;
} AizeBase;


#endif