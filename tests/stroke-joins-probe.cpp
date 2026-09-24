/* SPDX-License-Identifier: MIT
 * Compare an acute stroked path with an independent native Widen contour.
 * The near-reversing directions reproduce the Fenix route's captured join.
 */
#include <windows.h>
#include <d2d1_2.h>
#include <d3d11.h>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <cmath>
static void ck(HRESULT hr,const char *what){if(FAILED(hr)){printf("FAIL %s %08lx\n",what,hr);exit(2);}}
static ID2D1PathGeometry *path(ID2D1Factory *f,int shape){
 ID2D1PathGeometry *g;ID2D1GeometrySink *s;ck(f->CreatePathGeometry(&g),"path");ck(g->Open(&s),"sink");
 auto p=D2D1::Point2F(80,80);
 if(shape==0){ // The observed Fenix near-collinear tangents, meeting in opposite direction.
  s->BeginFigure(D2D1::Point2F(p.x-37.1866f,p.y+14.73624f),D2D1_FIGURE_BEGIN_HOLLOW);
  s->AddLine(p);s->AddLine(D2D1::Point2F(p.x-37.37f,p.y+14.26476f));
 }else if(shape==1){
  s->BeginFigure(D2D1::Point2F(40,50),D2D1_FIGURE_BEGIN_HOLLOW);s->AddLine(p);s->AddLine(D2D1::Point2F(40,51));
 }else if(shape==2){
  s->BeginFigure(D2D1::Point2F(40,80),D2D1_FIGURE_BEGIN_HOLLOW);s->AddLine(p);s->AddLine(D2D1::Point2F(40,80));
 }else{
  s->BeginFigure(D2D1::Point2F(40,80),D2D1_FIGURE_BEGIN_HOLLOW);s->AddLine(p);s->AddLine(D2D1::Point2F(80,40));
 }
 s->EndFigure(D2D1_FIGURE_END_OPEN);ck(s->Close(),"close");s->Release();return g;
}
int main(){
 ID3D11Device *gpu;ID3D11DeviceContext *imm;D3D_FEATURE_LEVEL level;
 ck(D3D11CreateDevice(NULL,D3D_DRIVER_TYPE_HARDWARE,NULL,D3D11_CREATE_DEVICE_BGRA_SUPPORT,NULL,0,D3D11_SDK_VERSION,&gpu,&level,&imm),"gpu");
 ID2D1Factory *f,*native;ck(D2D1CreateFactory(D2D1_FACTORY_TYPE_MULTI_THREADED,&f),"factory");
 auto mod=LoadLibraryExW(L"d2d1_geometry.dll",NULL,LOAD_LIBRARY_SEARCH_SYSTEM32);if(!mod)return 3;
 auto create=(HRESULT(WINAPI*)(D2D1_FACTORY_TYPE,REFIID,const D2D1_FACTORY_OPTIONS*,void**))GetProcAddress(mod,"D2D1CreateFactory");
 ck(create(D2D1_FACTORY_TYPE_MULTI_THREADED,__uuidof(ID2D1Factory),NULL,(void**)&native),"native factory");
 D3D11_TEXTURE2D_DESC d={};d.Width=d.Height=192;d.MipLevels=d.ArraySize=d.SampleDesc.Count=1;d.Format=DXGI_FORMAT_B8G8R8A8_UNORM;d.BindFlags=D3D11_BIND_RENDER_TARGET|D3D11_BIND_SHADER_RESOURCE;
 ID3D11Texture2D *tex,*stage;ck(gpu->CreateTexture2D(&d,NULL,&tex),"texture");d.Usage=D3D11_USAGE_STAGING;d.BindFlags=0;d.CPUAccessFlags=D3D11_CPU_ACCESS_READ;ck(gpu->CreateTexture2D(&d,NULL,&stage),"stage");
 IDXGISurface *surface;ck(tex->QueryInterface(__uuidof(IDXGISurface),(void**)&surface),"surface");
 auto rp=D2D1::RenderTargetProperties(D2D1_RENDER_TARGET_TYPE_DEFAULT,D2D1::PixelFormat(d.Format,D2D1_ALPHA_MODE_PREMULTIPLIED),96,96);
 ID2D1RenderTarget *target;ck(f->CreateDxgiSurfaceRenderTarget(surface,&rp,&target),"target");
 ID2D1DeviceContext1 *ctx;ck(target->QueryInterface(__uuidof(ID2D1DeviceContext1),(void**)&ctx),"ctx");
 ID2D1SolidColorBrush *brush;ck(ctx->CreateSolidColorBrush(D2D1::ColorF(0,1,0,1),&brush),"brush");
 int cases=0,failures=0,wrong=0;std::vector<unsigned> reference(192*192);
 for(int shape=0;shape<4;shape++)for(int join=0;join<4;join++)for(float limit:{0.f,1.f,4.f})for(int tr=0;tr<2;tr++)for(int variant=0;variant<4;variant++){
  auto geo=path(f,shape),ng=path(native,shape);auto props=D2D1::StrokeStyleProperties();props.lineJoin=(D2D1_LINE_JOIN)join;props.miterLimit=limit;
  float custom[]={1.5f,.5f,.25f,.75f};
  if(variant){props.startCap=(D2D1_CAP_STYLE)variant;props.endCap=(D2D1_CAP_STYLE)(4-variant);props.dashCap=(D2D1_CAP_STYLE)(variant%3);props.dashOffset=.4f;props.dashStyle=variant==1?D2D1_DASH_STYLE_DASH:variant==2?D2D1_DASH_STYLE_CUSTOM:D2D1_DASH_STYLE_DOT;}
  auto dashes=variant==2?custom:nullptr;auto count=variant==2?4:0;
  ID2D1StrokeStyle *style,*ns;ck(f->CreateStrokeStyle(props,dashes,count,&style),"style");ck(native->CreateStrokeStyle(props,dashes,count,&ns),"native style");
  ID2D1PathGeometry *wide;ID2D1GeometrySink *sink;ck(f->CreatePathGeometry(&wide),"wide");ck(wide->Open(&sink),"wide sink");ck(ng->Widen(3,ns,NULL,.05f,sink),"reference widen");ck(sink->Close(),"wide close");sink->Release();
  ID2D1GeometryRealization *real;ck(ctx->CreateStrokedGeometryRealization(geo,.05f,3,style,&real),"realization");
  int bad=0;
  for(int pass=0;pass<3;pass++){
   ctx->BeginDraw();ctx->Clear(D2D1::ColorF(0,0,0,0));ctx->SetAntialiasMode(D2D1_ANTIALIAS_MODE_ALIASED);
   ctx->SetTransform(tr?D2D1::Matrix3x2F::Rotation(35,D2D1::Point2F(80,80))*D2D1::Matrix3x2F::Scale(.8f,1.2f):D2D1::Matrix3x2F::Identity());
   if(pass==0)ctx->FillGeometry(wide,brush);else if(pass==1)ctx->DrawGeometry(geo,brush,3,style);else ctx->DrawGeometryRealization(real,brush);
   ck(ctx->EndDraw(),"end");imm->CopyResource(stage,tex);D3D11_MAPPED_SUBRESOURCE map;ck(imm->Map(stage,0,D3D11_MAP_READ,0,&map),"map");
   int mismatch=0;
   for(int y=0;y<192;y++)for(int x=0;x<192;x++){unsigned p=((unsigned*)((char*)map.pData+y*map.RowPitch))[x];if(!pass)reference[y*192+x]=p;else mismatch+=p!=reference[y*192+x];}
   imm->Unmap(stage,0);if(pass){wrong+=mismatch;bad+=mismatch>4;cases++;}
  }
  if(bad&&failures<8)printf("mismatch shape=%d join=%d limit=%g transform=%d style=%d\n",shape,join,limit,tr,variant);
  failures+=bad;real->Release();wide->Release();ns->Release();style->Release();ng->Release();geo->Release();
 }
 printf("Native stroke contour comparisons: %d cases, %d failures, %d differing pixels\n",cases,failures,wrong);
 brush->Release();ctx->Release();target->Release();surface->Release();stage->Release();tex->Release();native->Release();f->Release();imm->Release();gpu->Release();return failures?1:0;
}
