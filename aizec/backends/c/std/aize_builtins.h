#ifndef AIZE_BUILTINS_H
#define AIZE_BUILTINS_H
#include <stdlib.h>
#include "aize_common.h"


/******* Aize String *******/

struct AizeString {
    AizeBase base;
    size_t len;
    char* str;
};


/******* Aize List *******/

struct AizeList {
    AizeBase base;
    size_t len;
    size_t capacity;
    AizeObjectRef* arr;
};


extern void* AizeList_vtable[2];


AizeObjectRef AizeList_new();

void AizeList_append(AizeObjectRef, AizeObjectRef);

AizeObjectRef AizeList_get(AizeObjectRef, size_t);


/******* Aize Array *******/


struct AizeArray {
    AizeBase base;
    size_t len;
    AizeObjectRef* arr;
};

AizeObjectRef AizeArray_new(size_t);

AizeObjectRef AizeArray_get(AizeObjectRef, size_t);


/***** MEMORY MANAGEMENT *****/

extern uint32_t aize_mem_depth;

void aize_mem_init();

AizeBase* aize_mem_malloc(size_t);

void aize_mem_enter();

void aize_mem_exit();

AizeObjectRef aize_mem_ret(AizeObjectRef);

#endif