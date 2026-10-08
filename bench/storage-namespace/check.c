/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real 6502/cc65 ABI differential test. The unchanged C policy is the oracle. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "udeks/fs_namespace.h"
uint8_t reference_resolve(const uint8_t *,uint8_t,uint8_t,struct udeks_fs_path *);
uint8_t reference_device(const struct udeks_fs_volumes *,uint8_t,uint8_t *);
uint8_t reference_classify(const uint8_t *,uint8_t,struct udeks_fs_path *,uint8_t *);
uint8_t reference_physical(const struct udeks_fs_path *,uint8_t,uint8_t *);
uint8_t reference_consider(const struct udeks_fs_path *,const uint8_t *,uint8_t *);

struct guarded { uint8_t before; struct udeks_fs_path path; uint8_t after; };
static struct guarded actual, expected;
static uint8_t a[18],b[18],physical[16],path[32];
static struct udeks_fs_path query, invalid_query;
static struct udeks_fs_volumes volumes;
static uint8_t k,ra,rb;
static unsigned count, seed=1047;
static uint8_t next(void) { seed=seed*25173u+13849u; return seed>>8; }
static void reset(void) {
    memset(&actual,0x5a,sizeof(actual)); memset(&expected,0x5a,sizeof(expected));
    memset(a,0x5a,sizeof(a)); memset(b,0x5a,sizeof(b));
}
static uint8_t result(const char *name,uint8_t error) {
    ++count;
    if(ra!=rb || error) {
        printf("FAIL %s case %u: got %u expected %u output %u\n",name,count,ra,rb,error);
        return 1;
    }
    return 0;
}
static uint8_t resolve(const uint8_t *p,uint8_t n,uint8_t cwd,uint8_t null_out) {
    reset();
    rb=reference_resolve(p,n,cwd,null_out?0:&expected.path);
    ra=udeks_fs_resolve(p,n,cwd,null_out?0:&actual.path);
    return result("resolve",memcmp(&actual,&expected,sizeof(actual))!=0);
}
static uint8_t classify(const uint8_t *p,uint8_t data,uint8_t null_out,uint8_t null_kind) {
    reset();
    rb=reference_classify(p,data,null_out?0:&expected.path,null_kind?0:b+1);
    ra=udeks_fs_classify(p,data,null_out?0:&actual.path,null_kind?0:a+1);
    return result("classify",memcmp(&actual,&expected,sizeof(actual))!=0 || memcmp(a,b,sizeof(a))!=0);
}
static uint8_t device(const struct udeks_fs_volumes *v,uint8_t dir,uint8_t null_out) {
    reset();
    rb=reference_device(v,dir,null_out?0:b+1);
    ra=udeks_fs_device(v,dir,null_out?0:a+1);
    return result("device",memcmp(a,b,sizeof(a))!=0);
}
static uint8_t encode(const struct udeks_fs_path *q,uint8_t kind,uint8_t null_out) {
    reset();
    rb=reference_physical(q,kind,null_out?0:b+1);
    ra=udeks_fs_physical(q,kind,null_out?0:a+1);
    return result("physical",memcmp(a,b,sizeof(a))!=0);
}
static uint8_t consider(const struct udeks_fs_path *q,const uint8_t *p,uint8_t selected,uint8_t null_out) {
    reset(); a[1]=b[1]=selected;
    rb=reference_consider(q,p,null_out?0:b+1);
    ra=udeks_fs_consider(q,p,null_out?0:a+1);
    return result("consider",memcmp(a,b,sizeof(a))!=0);
}
static const char * const paths[]={
    "", "/", "//", "bin", "../etc/./rc", "/mnt/../bin/foo", "bin/foo/",
    "a/..", "a//b", "//bin///", "/bin/./../etc", "./..", "../../..", "...",
    "/bin/abcdefghijklmn", "/etc/abcdefghijklm", "/mnt/abcdefghijklmnop",
    "/bin/abcdefghijkl", "BIN", "ETC", "MNT", "/bin/.sh", "/  ",
    "a@b", "*", "?", "a,b", "a:b", "a=b", "/\xc1", "bin/./foo//.."
};
static const char * const names[]={
    "A", "FOO.BIN", "FOO.SH", "RC.ETC", "FOO.USR", "FOO.RC", "FOO.TXT",
    ".BIN", "..BIN", "...SH", ".", "..", "BIN", "ETC", "MNT", " ",
    "FOO BIN", "FOO-BIN", "ABCDEFGHIJKLMNOP", "\xc1.BIN"
};
static const char * const prefixes[]={"/","/bin/","/etc/","/mnt/"};
static const char * const suffixes[]={".BIN",".SH",".ETC",".TXT"};
static const uint8_t alphabet[]="aB09_-. ";

int main(void) {
    unsigned i,j,r;
    uint8_t n,c,d,code;
    if(sizeof(query)!=19 || sizeof(volumes)!=2 || (uint8_t *)&query.directory!=(uint8_t *)&query ||
       (uint8_t *)&query.length!=(uint8_t *)&query+1 || query.name!=(uint8_t *)&query+2) {
        puts("FAIL namespace C layout changed");return 1;
    }
    /* Pointers, lengths, delimiters, cwd limits and full-byte character set. */
    for(i=0;i<sizeof(paths)/sizeof(paths[0]);++i)
        for(d=0;d<6;++d) {
            n=strlen(paths[i]);
            if(resolve((const uint8_t *)paths[i],n,d,0)) return 1;
            if(n && resolve((const uint8_t *)paths[i],n-1,d,0)) return 1;
        }
    memset(path,'a',sizeof(path));
    for(n=0;n<26;++n) if(resolve(path,n,0,0)) return 1;
    if(resolve(0,3,0,0)||resolve(path,3,0,1)||resolve(path,3,255,0)) return 1;
    if(classify(0,0,0,0)||classify(physical,0,1,0)||classify(physical,0,0,1)) return 1;
    if(encode(0,1,0)||encode(&query,1,1)||consider(0,physical,0,0)||
        consider(&query,0,0,0)||consider(&query,physical,0,1)||device(0,0,0)||
        device(&volumes,0,1)||device(&volumes,255,0)) return 1;
    for(i=0;i<256;++i) {
        path[0]=i;
        if(resolve(path,1,0,0)) return 1;
        for(n=0;n<16;n+=7) {
            memset(physical,'A',sizeof(physical));physical[n]=i;
            for(d=0;d<3;++d) if(classify(physical,d,0,0)) return 1;
        }
        volumes.root=i;volumes.data=255-i;
        for(d=0;d<5;++d) if(device(&volumes,d,0)) return 1;
    }
    /* Seed a known query before testing invalid lengths and terminators. */
    reference_resolve((const uint8_t *)"/bin/foo",8,0,&query);
    for(d=0;d<5;++d) for(n=0;n<19;++n) {
        invalid_query=query;invalid_query.directory=d;invalid_query.length=n;
        for(k=0;k<6;++k) {
            if(encode(&invalid_query,k,0)) return 1;
            if(consider(&invalid_query,(const uint8_t *)"FOO.BIN\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0",k,0)) return 1;
        }
    }
    for(i=0;i<sizeof(names)/sizeof(names[0]);++i) {
        memset(physical,0xa0,16);memcpy(physical,names[i],strlen(names[i]));
        for(d=0;d<2;++d) {
            if(classify(physical,d,0,0)) return 1;
            for(k=0;k<6;++k) if(consider(&query,physical,k,0)) return 1;
        }
    }
    /* Deterministic valid/folded names, random malformed padding, inverse
     * translation, logical round trips and collisions. No libc rand state. */
    for(r=0;r<1000;++r) {
        n=1+(next()%12);memset(physical,0xa0,16);
        for(j=0;j<n;++j) physical[j]=alphabet[next()&7];
        k=next()&3;c=strlen(suffixes[k]);
        memcpy(physical+n,suffixes[k],c);
        if(r%5==0) physical[next()&15]=next();
        for(d=0;d<2;++d) {
            if(classify(physical,d,0,0)) return 1;
            code=reference_classify(physical,d,&query,&k);
            if(code) continue;
            for(k=0;k<6;++k) {
                if(encode(&query,k,0)||consider(&query,physical,k,0)) return 1;
            }
            n=strlen(prefixes[query.directory]);
            memcpy(path,prefixes[query.directory],n);memcpy(path+n,query.name,query.length);
            if(resolve(path,n+query.length,next()&3,0)) return 1;
            invalid_query=query;invalid_query.name[query.length]='X';
            if(encode(&invalid_query,1,0)||consider(&invalid_query,physical,0,0)) return 1;
            invalid_query=query;invalid_query.name[next()%query.length]='*';
            if(encode(&invalid_query,1,0)||consider(&invalid_query,physical,0,0)) return 1;
        }
    }
    printf("PASS %u namespace cases: real cc65 ABI, C oracle, guards and atomic rejection\n",count);
    return 0;
}
