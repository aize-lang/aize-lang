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


#define START_SIZE 256
#define SCALE_FACTOR 2
#define SHRINK_WHEN 4
#define SHRINK_FACTOR 2


struct AizeMemArrayList {
    size_t capacity;
    size_t len;
    AizeBase** arr;
};


struct AizeMemArrayList aize_mem_bound = {0, 0, 0};


uint32_t aize_mem_depth = 1;


void aize_mem_init() {
    aize_mem_bound.arr = malloc(START_SIZE);
    aize_mem_bound.capacity = START_SIZE;
}


void aize_mem_enter() {
    aize_mem_depth += 1;
}


void aize_mem_add_mem(void* mem) {
    if (aize_mem_bound.len == aize_mem_bound.capacity) {
        aize_mem_bound.arr = realloc(aize_mem_bound.arr, aize_mem_bound.capacity * SCALE_FACTOR);
        aize_mem_bound.capacity *= SCALE_FACTOR;
    }
    aize_mem_bound.arr[aize_mem_bound.len] = mem;
    aize_mem_bound.len += 1;
}


void aize_mem_pop_mem(size_t num) {
    memset(aize_mem_bound.arr + (aize_mem_bound.len-num), 0, num*sizeof(AizeBase**));
    aize_mem_bound.len -= num;
    if (aize_mem_bound.capacity > SCALE_FACTOR * START_SIZE &&
        aize_mem_bound.len - num < aize_mem_bound.capacity / SHRINK_WHEN)
    {
        aize_mem_bound.arr = realloc(aize_mem_bound.arr, aize_mem_bound.capacity / SCALE_FACTOR);
        aize_mem_bound.capacity /= SCALE_FACTOR;
    }
}


void* aize_mem_malloc(size_t bytes) {
    void* mem = malloc(bytes);
    aize_mem_add_mem(mem);
    return mem;
}


void aize_mem_collect() {
    int num_to_pop = 0;
    AizeBase* ret_obj = NULL;
    for (int i = aize_mem_bound.len-1; i >= 0; i--) {
        AizeBase* obj = aize_mem_bound.arr[i];
        if (obj->depth >= aize_mem_depth) {
            if (obj->ref_count != 0) {
                // TODO handle 'floating' objects eventually
            } else {
                free(obj);
            }
        } else if (obj->depth == 0) {  // returned object
            obj->depth = aize_mem_depth - 1;
            ret_obj = obj;
        } else {
            break;
        }
        num_to_pop++;
    }
    aize_mem_pop_mem(num_to_pop);
    if (ret_obj) {
        aize_mem_add_mem(ret_obj);
    }
}


void aize_mem_exit() {
    aize_mem_collect();
    aize_mem_depth -= 1;
}

