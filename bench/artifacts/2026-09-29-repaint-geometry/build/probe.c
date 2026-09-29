/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Actual 8502 ASM versus independent C arithmetic, never a production disk. */
#include <stddef.h>
#include <stdint.h>
struct window_prefix {
    unsigned char flags;
    unsigned int x;
    unsigned char y;
    unsigned int width;
    unsigned char height, rank;
};
unsigned int damage_left,damage_right;
unsigned char damage_top,damage_bottom;
extern void damage_set(const struct window_prefix *window);
extern void damage_add(const struct window_prefix *window);
#define R(n) (*(volatile unsigned char *)(0x7fc0u+(n)))
static const unsigned int xs[10]={0,1,15,16,255,256,303,319,32767,65535u};
static const unsigned int ws[10]={0,1,16,17,255,256,319,320,32767,65535u};
static const unsigned char ys[10]={0,1,17,18,127,182,199,200,254,255};
static const unsigned char hs[10]={0,1,17,18,48,104,199,200,254,255};
static unsigned char failed;
static void fail(unsigned char code) { if(!failed)failed=code; }
static void compare(unsigned int l,unsigned char t,unsigned int r,unsigned char b,unsigned char code)
{
    if(damage_left!=l || damage_top!=t || damage_right!=r || damage_bottom!=b)fail(code);
}
int main(void)
{
    struct window_prefix a,b;
    unsigned char i,j;
    unsigned int l,r,right;
    unsigned char t,bottom,lower;
    for(i=0;i<16u;++i) R(i)=0;
    R(0)='D';R(1)='G';R(2)='E';R(3)='O';R(4)=1;
    for(i=0;i<10u;++i)for(j=0;j<10u;++j) {
        a.flags=b.flags=0;a.rank=b.rank=1;
        a.x=xs[i];a.y=ys[j];a.width=ws[j];a.height=hs[i];
        b.x=xs[j];b.y=ys[i];b.width=ws[i];b.height=hs[j];
        damage_set(&a);
        l=a.x;t=a.y;r=(unsigned int)(a.x+a.width);bottom=(unsigned char)(a.y+a.height);
        compare(l,t,r,bottom,1);
        damage_add(&b);
        right=(unsigned int)(b.x+b.width);lower=(unsigned char)(b.y+b.height);
        if(b.x<l)l=b.x;if(b.y<t)t=b.y;
        if(right>r)r=right;if(lower>bottom)bottom=lower;
        compare(l,t,r,bottom,2);
        ++R(7);
    }
    if(offsetof(struct window_prefix,flags)!=0 || offsetof(struct window_prefix,x)!=1 ||
       offsetof(struct window_prefix,y)!=3 || offsetof(struct window_prefix,width)!=4 ||
       offsetof(struct window_prefix,height)!=6 || offsetof(struct window_prefix,rank)!=7 ||
       sizeof(struct window_prefix)!=8) fail(3);
    R(6)=failed;
    R(5)=2;
    return failed;
}
