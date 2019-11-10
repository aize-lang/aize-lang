
#include "aizeio.h"
#include "time.h"
#include <stdio.h>

void test() {
    printf("Hello world");
}


void print_int(int num, int newline) {
    if (newline)
        printf("%i\n", num);
    else
        printf("%i", num);
}

void print_space() {
    printf(" ");
}

int get_time() {
    return clock();
}

void print(AizeObjectRef obj) {
    printf("%p\n", obj.obj);
}