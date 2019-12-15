#include "aize_builtins.h"


uint32_t aize_mem_depth = 1;

/******* Memory Management *******/


#define START_SIZE 256
#define SCALE_FACTOR 2
#define SHRINK_WHEN 4
#define SHRINK_FACTOR 2

struct AizeArrayList {
    size_t capacity;
    size_t len;
    AizeBase** arr;
};


struct AizeArrayList aize_mem_bound = {0, 0, 0};


void aize_mem_init() {
    aize_mem_bound.arr = calloc(START_SIZE, sizeof(AizeBase**));
    aize_mem_bound.capacity = START_SIZE;
}


void aize_mem_enter() {
    aize_mem_depth += 1;
}


void aize_mem_add_mem(AizeBase* mem) {
    #ifdef DEBUG
        printf("Adding %p\n", mem);
    #endif
    if (aize_mem_bound.len == aize_mem_bound.capacity) {
        // printf("Resizing\n");
        aize_mem_bound.arr = realloc(aize_mem_bound.arr, aize_mem_bound.capacity * SCALE_FACTOR * sizeof(AizeBase**));
        aize_mem_bound.capacity *= SCALE_FACTOR;
    }
    aize_mem_bound.arr[aize_mem_bound.len] = mem;
    aize_mem_bound.len += 1;
}


void aize_mem_pop_mem(size_t num) {
    #ifdef DEBUG
        printf("Popping %i\n", num);
    #endif
    // memset(aize_mem_bound.arr + (aize_mem_bound.len-num), 0, num*sizeof(AizeBase**));
    aize_mem_bound.len -= num;
    if (aize_mem_bound.capacity >= SHRINK_FACTOR * START_SIZE &&
        aize_mem_bound.len < aize_mem_bound.capacity / SHRINK_WHEN)
    {
        // printf("Resizing\n");
        aize_mem_bound.arr = realloc(aize_mem_bound.arr, aize_mem_bound.capacity / SHRINK_FACTOR);
        aize_mem_bound.capacity /= SHRINK_FACTOR;
    }
}


AizeBase* aize_mem_malloc(size_t bytes) {
    AizeBase* mem = malloc(bytes);
    #ifdef DEBUG
        printf("Malloc'ed: %p at depth %i\n", mem, aize_mem_depth);
    #endif
    mem->depth = aize_mem_depth;
    aize_mem_add_mem(mem);
    return mem;
}


void aize_mem_collect() {
    #ifdef DEBUG
        printf("Checking depth %i\n", aize_mem_depth);
    #endif
    int num_to_pop = 0;
    AizeBase* ret_obj = NULL;
    for (int i = aize_mem_bound.len-1; i >= 0; i--) {
        #ifdef DEBUG
            printf("On %i\n", i);
        #endif
        AizeBase* obj = aize_mem_bound.arr[i];
        if (obj->depth >= aize_mem_depth) {
            if (obj->ref_count != 0) {
                #ifdef DEBUG
                    printf("Floating: %p at depth %i\n", obj, obj->depth);
                #endif
                // TODO handle 'floating' objects eventually
            } else {
                #ifdef DEBUG
                    printf("Freed: %p at depth %i\n", obj, obj->depth);
                #endif
                free(obj);
            }
        } else if (obj->depth == 0) {  // returned object
            ret_obj = obj;
            #ifdef DEBUG
                printf("Ret Obj: %p, %p\n", obj, ret_obj);
            #endif
        } else {
            break;
        }
        num_to_pop++;
    }
    aize_mem_pop_mem(num_to_pop);
    if (ret_obj) {
        #ifdef DEBUG
            printf("Returning %p\n", ret_obj);
        #endif
        ret_obj->depth = aize_mem_depth - 1;
        aize_mem_add_mem(ret_obj);
    }
    #ifdef DEBUG
        printf("Popped: %i\n", num_to_pop);
    #endif
}


void aize_mem_exit() {
    aize_mem_collect();
    aize_mem_depth -= 1;
}


AizeObjectRef aize_mem_ret(AizeObjectRef obj) {
    if (obj.obj->depth >= aize_mem_depth) {
        obj.obj->depth = 0;
    }
    aize_mem_exit();
    // printf("Ret depth: %i\n", obj->depth);
    return obj;
}
