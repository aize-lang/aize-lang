#ifndef AIZE_BUILTINS_H
#define AIZE_BUILTINS_H
#include "aize_common.h"


struct AizeObject {
    struct AizeBase base;
};


extern void* AizeObject_vtable[0];

#endif