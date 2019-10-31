#ifndef AIZE_BUILTINS_H
#define AIZE_BUILTINS_H
#include <stdlib.h>
#include "aize_common.h"


struct AizeObject {
    struct AizeBase base;
};

extern void* AizeObject_vtable[0];

struct AizeList {
    struct AizeObject base;
    size_t len;
    size_t capacity;
    AizeBase** arr;
};


extern void* AizeList_vtable[2];


struct AizeList* AizeList_new();

void AizeList_append(struct AizeList*, AizeBase*);

AizeBase* AizeList_get(struct AizeList*, size_t);


/***** MEMORY MANAGEMENT *****/

extern uint32_t aize_mem_depth;

void aize_mem_init();

void* aize_mem_malloc(size_t);

void aize_mem_enter();

void aize_mem_exit();

AizeBase* aize_mem_ret(AizeBase*);

#endif