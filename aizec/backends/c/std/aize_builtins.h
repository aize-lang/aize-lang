#ifndef AIZE_BUILTINS_H
#define AIZE_BUILTINS_H
#include <stdlib.h>
#include "aize_common.h"


struct AizeObject {
    struct AizeBase base;
};


extern void* AizeObject_vtable[0];


typedef struct AizeListRef {
    void** vtable;
    struct AizeList* obj;
} AizeListRef;


struct AizeList {
    struct AizeObject base;
    size_t len;
    size_t capacity;
    AizeObjectRef* arr;
};


extern void* AizeList_vtable[2];


AizeObjectRef AizeList_new();

void AizeList_append(AizeObjectRef, AizeObjectRef);

AizeObjectRef AizeList_get(AizeObjectRef, size_t);


/***** MEMORY MANAGEMENT *****/

extern uint32_t aize_mem_depth;

void aize_mem_init();

AizeBase* aize_mem_malloc(size_t);

void aize_mem_enter();

void aize_mem_exit();

AizeObjectRef aize_mem_ret(AizeObjectRef);

#endif