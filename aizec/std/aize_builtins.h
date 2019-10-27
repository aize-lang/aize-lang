#ifndef AIZE_BUILTINS_H
#define AIZE_BUILTINS_H
#include <stdlib.h>
#include "aize_common.h"


struct AizeObject {
    struct AizeBase base;
};


extern void* AizeObject_vtable[0];


void* aize_mem_malloc(size_t);

void aize_mem_enter();

void aize_mem_exit();

#endif