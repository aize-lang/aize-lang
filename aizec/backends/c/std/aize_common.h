#ifndef AIZE_COMMON_H
#define AIZE_COMMON_H
#include "stdint.h"


struct AizeObjectRef;
struct AizeBase;


typedef struct AizeBase {
    uint32_t depth;
    size_t ref_count;
    void (*on_free)(struct AizeObjectRef);
} AizeBase;


typedef struct AizeObjectRef {
    AizeBase* obj;
    uint32_t typeid;
} AizeObjectRef;


#endif