/* RGB pixel frames (512 x 288), followed by drift-free 24 Hz H.264 samples.
   Each record is one hold-count byte followed by the unscaled RGB bitmap. */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define H264E_SVC_API 0
#define H264E_MAX_THREADS 0
#define MINIH264_IMPLEMENTATION
#include "minih264e.h"
enum { SW=512, SH=288, W=1920, H=1080 };
static uint8_t rgb[SH][SW][3], lum[SH][SW], cb[SH][SW], cr[SH][SW];
static uint8_t planes[W*H*3/2] __attribute__((aligned(64)));
static void scale_frame(void){
    for(int y=0;y<SH;y++)for(int x=0;x<SW;x++){
        int r=rgb[y][x][0],g=rgb[y][x][1],b=rgb[y][x][2];
        lum[y][x]=16+((47*r+157*g+16*b+128)>>8);
        cb[y][x]=128+((-26*r-87*g+113*b+128)>>8);
        cr[y][x]=128+((112*r-102*g-10*b+128)>>8);
    }
    int sx[W],sy[H];
    for(int x=0;x<W;x++)sx[x]=(2*x+1)*SW/(2*W);
    for(int y=0;y<H;y++)sy[y]=(2*y+1)*SH/(2*H);
    for(int y=0;y<H;y++){
        uint8_t *dst=planes+y*W;
        const uint8_t *row=lum[sy[y]];
        /* Fine, low-contrast CRT phosphor lines at output resolution. */
        for(int x=0;x<W;x++){int v=row[sx[x]];dst[x]=((y%4)==3)?16+((v-16)*96+50)/100:v;}
    }
    for(int y=0;y<H/2;y++)for(int x=0;x<W/2;x++){
        int pix=y*(W/2)+x;int a=sy[2*y],b=sy[2*y+1],c=sx[2*x],d=sx[2*x+1];
        planes[W*H+pix]=(cb[a][c]+cb[a][d]+cb[b][c]+cb[b][d]+2)/4;
        planes[W*H*5/4+pix]=(cr[a][c]+cr[a][d]+cr[b][c]+cr[b][d]+2)/4;
    }
}
int main(void){
    H264E_create_param_t cfg={0};cfg.width=W;cfg.height=H;cfg.gop=96;cfg.const_input_flag=1;cfg.enableNEON=1;
    int a,b,st=H264E_sizeof(&cfg,&a,&b);if(st)return st;
    H264E_persist_t *ctx=malloc(a);H264E_scratch_t *scratch=malloc(b);
    if(!ctx||!scratch)return 100;
    st=H264E_init(ctx,&cfg);if(st)return st;
    H264E_io_yuv_t io={{planes,planes+W*H,planes+W*H*5/4},{W,W/2,W/2}};
    H264E_run_param_t settings={0};settings.encode_speed=8;settings.qp_min=24;settings.qp_max=26;settings.desired_frame_bytes=30000;
    int hold;
    while((hold=getchar())!=EOF){
        if(hold<1||hold>24||fread(rgb,1,sizeof(rgb),stdin)!=sizeof(rgb))return 101;
        scale_frame();
        for(int i=0;i<hold;i++){
            unsigned char *data;int len;
            st=H264E_encode(ctx,scratch,&settings,&io,&data,&len);if(st)return st;
            if(fwrite(data,1,len,stdout)!=(size_t)len)return 102;
        }
    }
    free(scratch);free(ctx);return ferror(stdin)||ferror(stdout);
}
