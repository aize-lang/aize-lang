#ifndef AIZE_BUILTINS_H
#define AIZE_BUILTINS_H
#include <stdlib.h>
#include "aize_common.h"


/***** MEMORY MANAGEMENT *****/

extern uint32_t aize_mem_depth;

void aize_mem_init();

AizeBase* aize_mem_malloc(size_t);

void aize_mem_enter();

void aize_mem_exit();

AizeObjectRef aize_mem_ret(AizeObjectRef);

#endif