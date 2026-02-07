#include <riscv_vector.h>
#include <stdio.h>

#define N 16

/*
* This code is intended to multiply elements of two arrays `a` and `b`
* only at even indices and store the result in array `c`. However, there
* is a bug in the logic.
* The vectors a and b are initialized as follows:
* a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
* b = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30]
* The expected output in c should therefore be:
* c = [0*0, 0, 2*4, 0, 4*8, 0, 6*12, 0, 8*16, 0, 10*20, 0, 12*24, 0, 14*28, 0]
*/

int main() {
    int a[N], b[N], c[N];
    for (int i = 0; i < N; i++) {
        a[i] = i;
        b[i] = 2*i;
        c[i] = 0;
    }

    size_t vl;
    vint32m1_t vzero = __riscv_vmv_v_x_i32m1(0, vl);
    for (int i = 0; i < N; i += (vl = __riscv_vsetvl_e32m1(N-i))) {
        vint32m1_t va = __riscv_vle32_v_i32m1(&a[i], vl);
        vint32m1_t vb = __riscv_vle32_v_i32m1(&b[i], vl);

        vbool32_t mask = __riscv_vmseq_vx_i32m1_b32(__riscv_vand_vx_i32m1(va, 1, vl), 0, vl);
        mask = __riscv_vmnot_m_b32(mask, vl);

        vint32m1_t vc = __riscv_vmul_vv_i32m1_mu(mask, vzero, va, vb, vl);
        __riscv_vse32_v_i32m1(&c[i], vc, vl);
    }

    for (int i = 0; i < N; i++) {
        printf("c[%d] = %d\n", i, c[i]);
    }
}