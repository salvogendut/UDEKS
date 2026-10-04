/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/clock_face.h"

static const signed char sin64[60] = {
      0,  7, 13, 20, 26, 32, 38, 43, 48, 52, 55, 58,
     61, 63, 64, 64, 64, 63, 61, 58, 55, 52, 48, 43,
     38, 32, 26, 20, 13,  7,  0, -7,-13,-20,-26,-32,
    -38,-43,-48,-52,-55,-58,-61,-63,-64,-64,-64,-63,
    -61,-58,-55,-52,-48,-43,-38,-32,-26,-20,-13, -7
};
static const unsigned char digits[11][5] = {
    {7,5,5,5,7}, {2,6,2,2,7}, {7,1,7,4,7}, {7,1,7,1,7},
    {5,5,7,1,1}, {7,4,7,1,7}, {7,4,7,5,7}, {7,1,1,1,1},
    {7,5,7,5,7}, {7,5,7,1,7}, {0,2,0,2,0}
};
/* Serialized per task; these variables belong to its relocated private BSS,
 * never the resident runtime or a shared application-status record. */
static unsigned char *out;
static unsigned char count;

static signed char component(unsigned char position, unsigned char radius)
{
    signed char value;
    unsigned char magnitude;
    value=sin64[position];
    magnitude=(unsigned int)(value<0 ? -value : value)*radius/64u;
    return value<0 ? -magnitude : magnitude;
}

static void point(unsigned char position, unsigned char radius)
{
    *out++=36+component(position,radius);
    position+=15;
    if(position>=60) position-=60;
    *out++=40-component(position,radius);
}

static void edge(unsigned char position, unsigned char next, unsigned char radius)
{
    *out++=1;
    point(position,24);
    point(next,radius);
    out+=3;                         /* color and reserved bytes are zero */
}

static void hand(unsigned char position, unsigned char radius)
{
    *out++=1; *out++=36; *out++=40;
    point(position,radius);
    out+=3;
}

unsigned char udeks_clock_face(unsigned char hour, unsigned char minute,
                             unsigned char *commands)
{
    unsigned int i;
    unsigned char position,next,digit,row;
    if(hour>23 || minute>59) return 0; /* atomic rejection of invalid time */
    for(i=0;i<UDEKS_CLOCK_FACE_COMMANDS*8u;++i) commands[i]=0;
    out=commands;
    position=0;
    for(count=0;count<24;++count) {
        next=position+((count&1)?3:2);
        if(next==60) next=0;
        edge(position,next,24);
        position=next;
    }
    for(position=0;position<60;position+=5) edge(position,position,21);
    hand((hour%12u)*5u+minute/12u,12);
    hand(minute,18);
    for(count=0;count<5;++count) {
        digit=count==0 ? hour/10u : count==1 ? hour%10u :
              count==2 ? 10u : count==3 ? minute/10u : minute%10u;
        *out++=2; *out++=17+count*8u; *out++=72;
        for(row=0;row<5;++row) *out++=digits[digit][row];
    }
    return UDEKS_CLOCK_FACE_COMMANDS;
}
