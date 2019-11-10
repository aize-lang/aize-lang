#ifndef AIZE_COMMON_H
#define AIZE_COMMON_H
#include "stdint.h"


typedef struct AizeBase {
    uint32_t depth;
    size_t ref_count;
} AizeBase;


typedef struct AizeObjectRef {
    void** vtable;
    AizeBase* obj;
} AizeObjectRef;


#endif