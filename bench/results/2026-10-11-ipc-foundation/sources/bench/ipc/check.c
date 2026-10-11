/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern const unsigned char root_image[],router_image[],vectors_image[],hidden_image[],bootfs_image[],common_image[];
extern const unsigned int ipc_state_address,ipc_serial_address;
extern unsigned int module_entry;
extern unsigned char module_hour,module_minute,module_second,module_stack_error;
unsigned char module_call(void);
#define REC ((unsigned char *)0xf359)
#define P (REC+14)
#define MEM(a) (*(unsigned char *)(a))
#define CHECK(c) check((c),__LINE__)
static unsigned int calls,iteration;
static unsigned char seq,rc,saved[62],payload[24],i;
static unsigned int h1,h2,h3;
static void check(unsigned char condition,unsigned int line)
{
    if(!condition) { printf("FAIL IPC line %u iteration %u call %u errno %u count %u\n",line,iteration,calls,REC[12],REC[10]);exit(1); }
}
static unsigned int word(const unsigned char *p) { return p[0]|((unsigned int)p[1]<<8); }
static void put(unsigned char *p,unsigned int v) { p[0]=v;p[1]=v>>8; }
static unsigned char invoke(unsigned int entry,unsigned char a)
{
    module_entry=entry;module_hour=a;module_minute=0x5a;module_second=0xa5;
    rc=module_call(); ++calls; CHECK(!module_stack_error); return rc;
}
static void request(unsigned char caller,unsigned char op,unsigned char count)
{
    memset(REC,0xa5,38);memcpy(REC,"UTRQ",4);REC[4]=0;REC[5]=21;REC[6]=1;
    REC[7]=29;REC[8]=++seq;REC[9]=op;REC[10]=count;REC[13]=0;MEM(0xf110)=caller;
}
static void submit(unsigned char error)
{
    memcpy(saved,(void *)ipc_state_address,62);invoke(0xcf30,0);
    CHECK(REC[8]==seq);CHECK(REC[6]==(error?128:2));CHECK(REC[12]==error);
    CHECK(REC[11]==(error?0:REC[10]));
    if(error) CHECK(!memcmp(saved,(void *)ipc_state_address,62));
}
static unsigned int create(unsigned char caller,const char *name)
{
    request(caller,0,strlen(name));memcpy(P,name,strlen(name));submit(0);CHECK(REC[10]==2);return word(P);
}
static void send(unsigned char caller,unsigned int destination,unsigned int source,unsigned char length,unsigned char error)
{
    request(caller,2,length+4);put(P,destination);put(P+2,source);
    for(i=0;i<length && i<20;++i) P[4+i]=i*17+iteration;
    memcpy(payload,P,24);submit(error);
}
static void receive(unsigned char caller,unsigned int handle,unsigned char capacity,unsigned char error)
{
    request(caller,3,3);put(P,handle);P[2]=capacity;submit(error);
}
static void close_endpoint(unsigned char caller,unsigned int handle,unsigned char error)
{ request(caller,4,2);put(P,handle);submit(error); }
static void retire(unsigned char caller)
{
    memcpy(payload,REC+14,24);CHECK(invoke(0xc883,caller)==caller);
    CHECK(!memcmp(payload,REC+14,24));
}
/* Independent queue oracle for a varied sequence of sends, receives and closes. */
struct endpoint { unsigned int handle,sender;unsigned char owner,length,bytes[16]; };
static struct endpoint model[2];
static unsigned int seed=0x1357;
static unsigned int random16(void) { seed=seed*109+89;return seed; }
static void differential(void)
{
    unsigned char a,b,op,caller,count,error,k;
    unsigned int handle;
    for(iteration=0;iteration<3000;++iteration) {
        a=random16()&1;b=a^1;op=(random16()>>2)%4;caller=1+((random16()>>5)%3);
        if(!model[a].owner) { model[a].handle=create(a+1,a?"beta":"alpha");model[a].owner=a+1;model[a].length=0; }
        if(!model[b].owner) { model[b].handle=create(b+1,b?"beta":"alpha");model[b].owner=b+1;model[b].length=0; }
        handle=model[a].handle;
        if(op==0) {
            count=1+(random16()%16);error=caller!=model[b].owner?13:(model[a].length?11:0);
            send(caller,handle,model[b].handle,count,error);
            if(!error) { model[a].length=count;model[a].sender=model[b].handle;memcpy(model[a].bytes,payload+4,count); }
        } else if(op==1) {
            count=random16()%17;error=caller!=model[a].owner?13:(!model[a].length?11:(count<model[a].length?90:0));
            receive(caller,handle,count,error);
            if(!error) { CHECK(word(P)==model[a].sender);CHECK(REC[10]==model[a].length+2);CHECK(!memcmp(P+2,model[a].bytes,model[a].length));model[a].length=0; }
        } else if(op==2) {
            error=caller!=model[a].owner?13:0;close_endpoint(caller,handle,error);
            if(!error) { model[a].owner=0;model[a].length=0;if(model[b].sender==handle)model[b].length=0; }
        } else {
            retire(caller);
            for(k=0;k<2;++k) if(model[k].owner==caller) {
                if(model[k^1].sender==model[k].handle)model[k^1].length=0;
                model[k].owner=0;model[k].length=0;
            }
        }
    }
    retire(1);retire(2);
}
int main(void)
{
    memcpy((void *)0x8000,root_image,0x1000);memcpy((void *)0xc880,router_image,0x80);
    memcpy((void *)0xcf00,vectors_image,0x100);memcpy((void *)0xd000,hidden_image,0x1000);
    memcpy((void *)0xf3ef,bootfs_image,0x29b);memcpy((void *)0xf800,common_image,0x109);
    MEM(0xfe20)=0xa9;MEM(0xfe21)=0;MEM(0xfe22)=0x60; /* unrelated storage transport */
    request(0,0,1);P[0]='a';submit(13);
    request(9,0,1);P[0]='a';submit(13);
    request(1,0,1);P[0]='a';REC[5]=20;submit(22);
    request(1,0,1);P[0]='a';REC[5]=22;submit(71);
    request(1,0,1);P[0]='a';REC[0]='x';submit(71);
    request(1,0,1);P[0]='a';REC[13]=1;submit(22);
    request(1,5,1);P[0]='a';submit(22);
    request(1,0,0);submit(22);
    request(1,0,9);submit(22);
    request(1,0,1);P[0]=0;submit(22);
    request(1,0,1);P[0]=' ';submit(22);
    request(1,0,1);P[0]=127;submit(22);
    h1=create(1,"server");h2=create(2,"client");CHECK(h1 && h2 && h1!=h2);
    request(3,0,6);memcpy(P,"server",6);submit(17);
    request(3,0,5);memcpy(P,"third",5);submit(28);
    request(3,1,6);memcpy(P,"server",6);submit(0);CHECK(word(P)==h1);
    request(3,1,5);memcpy(P,"serve",5);submit(2);
    receive(1,h1,16,11);receive(2,h1,16,13);
    close_endpoint(2,h1,13);close_endpoint(1,0,9);
    send(3,h1,h2,16,13);send(2,h1,h2,0,22);send(2,h1,h2,17,22);
    send(2,h1,h2,16,0);send(2,h1,h2,1,11);
    receive(1,h1,15,90);receive(1,h1,16,0);CHECK(word(P)==h2);
    for(i=0;i<16;++i)CHECK(P[2+i]==(unsigned char)(i*17));
    receive(1,h1,16,11);
    send(2,h1,h2,3,0);retire(2);receive(1,h1,16,11);
    send(2,h1,h2,1,9);h3=create(2,"client");CHECK(h3!=h2);
    receive(2,h2,16,9);send(1,h3,h1,1,0);close_endpoint(1,h1,0);receive(2,h3,16,11);
    close_endpoint(2,h3,0);
    h1=create(1,"12345678");h2=create(1,"second");send(1,h1,h2,1,0);retire(1);
    receive(1,h1,16,9);receive(1,h2,16,9);
    differential();
    /* Exhaustion must fail closed, including after the final live handle closes. */
    while(word((const unsigned char *)ipc_serial_address)!=65535u) {
        h1=create(1,"last");close_endpoint(1,h1,0);
    }
    request(1,0,4);memcpy(P,"last",4);submit(28);
    CHECK(word((const unsigned char *)ipc_serial_address)==65535u);
    printf("PASS IPC: queue/ownership/error/retirement checks, 3000 differential steps, handle exhaustion; %u calls (mod 65536)\n",calls);
    return 0;
}
