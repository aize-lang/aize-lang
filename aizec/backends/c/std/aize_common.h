#ifndef AIZE_COMMON_H
#define AIZE_COMMON_H
#include "stdint.h"


typedef struct AizeBase {
    uint32_t depth;
    size_t ref_count;
} AizeBase;


typedef struct AizeObjectRef {
    AizeBase* obj;
    uint32_t typeid;
} AizeObjectRef;


#endif