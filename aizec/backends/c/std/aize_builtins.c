#include "aize_builtins.h"


uint32_t aize_mem_depth = 1;


/******* Aize Object *******/


void* AizeObject_vtable[0] = { };


AizeObjectRef AizeObject_new_AizeObject(AizeObjectRef mem) {
    if (mem.obj == NULL) {
        mem.obj = malloc(sizeof(struct AizeObject));
    }
    mem.vtable = AizeObject_vtable;
    mem.obj->depth = aize_mem_depth;
    return mem;
}


/******* Aize List *******/


#define LIST_START_SIZE 16
#define LIST_SCALE_FACTOR 2
#define LIST_SHRINK_WHEN 4
#define LIST_SHRINK_FACTOR 2


void* AizeList_vtable[2] = {&AizeList_append, &AizeList_get};


AizeObjectRef AizeList_new() {
    struct AizeList* mem = aize_mem_malloc(sizeof(struct AizeList));
    mem->len = 0;
    mem->capacity = LIST_START_SIZE;
    mem->arr = calloc(LIST_START_SIZE, sizeof(AizeObjectRef));
    return (AizeObjectRef) {AizeList_vtable, mem};
}


void AizeList_append(AizeObjectRef li, AizeObjectRef obj) {
    struct AizeList* list = li.obj;
    if (list->len == list->capacity) {
        list->arr = realloc(list->arr, list->capacity * LIST_SCALE_FACTOR);
        list->capacity *= LIST_SCALE_FACTOR;
    }
    list->arr[list->len] = obj;
    list->len++;
}


AizeObjectRef AizeList_get(AizeObjectRef li, size_t item) {
    struct AizeList* list = li.obj;
    if (item >= 0 && item < list->len) {
        return (AizeObjectRef) list->arr[item];
    } else {
        return (AizeObjectRef) {NULL, NULL};
    }
}


/******* Aize String *******/


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
    if (aize_mem_bound.len == aize_mem_bound.capacity) {
        // printf("Resizing\n");
        aize_mem_bound.arr = realloc(aize_mem_bound.arr, aize_mem_bound.capacity * SCALE_FACTOR * sizeof(AizeBase**));
        aize_mem_bound.capacity *= SCALE_FACTOR;
    }
    aize_mem_bound.arr[aize_mem_bound.len] = mem;
    aize_mem_bound.len += 1;
}


void aize_mem_pop_mem(size_t num) {
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
    // printf("Malloc'ed: %p at depth %i\n", mem, aize_mem_depth);
    mem->depth = aize_mem_depth;
    aize_mem_add_mem(mem);
    return mem;
}


void aize_mem_collect() {
    // printf("Checking depth %i\n", aize_mem_depth);
    int num_to_pop = 0;
    AizeBase* ret_obj = NULL;
    for (int i = aize_mem_bound.len-1; i >= 0; i--) {
        // printf("On %i\n", i);
        AizeBase* obj = aize_mem_bound.arr[i];
        if (obj->depth >= aize_mem_depth) {
            if (obj->ref_count != 0) {
                // printf("Floating: %p at depth %i\n", obj, obj->depth);
                // TODO handle 'floating' objects eventually
            } else {
                // printf("Freed: %p at depth %i\n", obj, obj->depth);
                free(obj);
            }
        } else if (obj->depth == 0) {  // returned object
            ret_obj = obj;
            // printf("Ret Obj: %p, %p\n", obj, ret_obj);
        } else {
            break;
        }
        num_to_pop++;
    }
    aize_mem_pop_mem(num_to_pop);
    if (ret_obj) {
        // printf("Returning %p\n", ret_obj);
        ret_obj->depth = aize_mem_depth - 1;
        aize_mem_add_mem(ret_obj);
    }
    // printf("Popped: %i\n", num_to_pop);
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
