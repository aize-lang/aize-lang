#include "aize_builtins.h"


extern uint32_t aize_mem_depth;


void* AizeObject_vtable[0] = {
    // struct AizeString* (*AizeObject_to_string)(struct AizeObject*)
};


struct AizeObject* AizeObject_new_AizeObject(struct AizeObject* mem) {
    if (mem == NULL) {
        mem = (struct AizeObject*) malloc(sizeof(struct AizeObject));
    }
    (*mem).base.vtable = AizeObject_vtable;
    (*mem).base.depth = aize_mem_depth;
    return mem;
}
