/* SPDX-License-Identifier: MIT
 * Compare Wine objects with independently constructed native geometry objects.
 * The reference DLL is locally installed, never part of the patch distribution.
 */
#include <windows.h>
#include <d2d1.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <thread>
#include <atomic>
#include <vector>

static void check(HRESULT hr, const char *step)
{
    if (FAILED(hr)) { printf("FAIL %s: %08lx\n", step, hr); exit(2); }
}

static ID2D1Geometry *shape(ID2D1Factory *f, int kind)
{
    if (kind == 0) {
        ID2D1RectangleGeometry *g;
        check(f->CreateRectangleGeometry(D2D1::RectF(2,3,32,23), &g), "rectangle"); return g;
    }
    if (kind == 1) {
        ID2D1EllipseGeometry *g;
        check(f->CreateEllipseGeometry(D2D1::Ellipse(D2D1::Point2F(3,5),20,8), &g), "ellipse"); return g;
    }
    if (kind == 2) {
        ID2D1RoundedRectangleGeometry *g;
        check(f->CreateRoundedRectangleGeometry(D2D1::RoundedRect(D2D1::RectF(0,0,30,20),4,3), &g), "rounded"); return g;
    }
    if (kind == 3) {
        auto original = shape(f,6); ID2D1TransformedGeometry *g;
        check(f->CreateTransformedGeometry(original,D2D1::Matrix3x2F::Rotation(37) * D2D1::Matrix3x2F::Scale(2,.5), &g),"transformed");
        original->Release(); return g;
    }
    if (kind == 4 || kind == 5) {
        ID2D1Geometry *items[] = {shape(f,0),shape(f,6)}; ID2D1GeometryGroup *g;
        check(f->CreateGeometryGroup(kind == 4 ? D2D1_FILL_MODE_ALTERNATE : D2D1_FILL_MODE_WINDING,items,2,&g),"group");
        for(auto item : items) item->Release(); return g;
    }
    ID2D1PathGeometry *g; ID2D1GeometrySink *s;
    check(f->CreatePathGeometry(&g),"path"); check(g->Open(&s),"open");
    if (kind == 6) {
        s->BeginFigure(D2D1::Point2F(0,0),D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddBezier(D2D1::BezierSegment(D2D1::Point2F(25,-14),D2D1::Point2F(42,38),D2D1::Point2F(8,20)));
        s->AddQuadraticBezier(D2D1::QuadraticBezierSegment(D2D1::Point2F(-12,32),D2D1::Point2F(0,0)));
        s->EndFigure(D2D1_FIGURE_END_CLOSED);
    } else if (kind == 7 || kind == 9) {
        s->BeginFigure(D2D1::Point2F(0,0),D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddLine(D2D1::Point2F(0,0));
        s->AddLine(D2D1::Point2F(3,4));
        s->AddLine(D2D1::Point2F(8,4));
        s->EndFigure(kind == 9 ? D2D1_FIGURE_END_CLOSED : D2D1_FIGURE_END_OPEN);
        s->BeginFigure(D2D1::Point2F(100,100),D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddLine(D2D1::Point2F(103,104));
        s->EndFigure(D2D1_FIGURE_END_OPEN);
    } else if (kind == 10) {
        s->BeginFigure(D2D1::Point2F(5,7),D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddLine(D2D1::Point2F(5,7));
        s->EndFigure(D2D1_FIGURE_END_OPEN);
    } else if (kind == 11) {
        s->BeginFigure(D2D1::Point2F(0,0),D2D1_FIGURE_BEGIN_HOLLOW);
        s->AddArc(D2D1::ArcSegment(D2D1::Point2F(25,20),D2D1::SizeF(22,15),30,
                  D2D1_SWEEP_DIRECTION_CLOCKWISE,D2D1_ARC_SIZE_LARGE));
        s->EndFigure(D2D1_FIGURE_END_OPEN);
    } // kind 8 is empty.
    check(s->Close(),"close"); s->Release(); return g;
}

static bool close_float(float a, float b, float tolerance)
{
    return (std::isnan(a) && std::isnan(b)) || a == b || std::fabs(a-b) <= tolerance;
}

int main(int argc, char **argv)
{
    ID2D1Factory *f, *ref;
    check(D2D1CreateFactory(D2D1_FACTORY_TYPE_MULTI_THREADED,&f),"factory");
    if (argc > 1 && !strcmp(argv[1],"--disabled")) {
        auto g = shape(f,7); float len=0; D2D1_POINT_2F point,tangent;
        auto a=g->ComputeLength(nullptr,.1f,&len);
        auto b=g->ComputePointAtLength(3,nullptr,.1f,&point,&tangent);
        printf("Scope control length=%08lx point=%08lx expected=80004001\n",a,b);
        g->Release(); f->Release(); return a != E_NOTIMPL || b != E_NOTIMPL;
    }
    HMODULE module = LoadLibraryExW(L"d2d1_geometry.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!module) return 3;
    auto create=(HRESULT (WINAPI *)(D2D1_FACTORY_TYPE,REFIID,const D2D1_FACTORY_OPTIONS*,void**))GetProcAddress(module,"D2D1CreateFactory");
    if (!create) return 4;
    check(create(D2D1_FACTORY_TYPE_MULTI_THREADED,__uuidof(ID2D1Factory),nullptr,(void**)&ref),"reference");
    int cases=0, failures=0;
    auto transformed=D2D1::Matrix3x2F::Rotation(24) * D2D1::Matrix3x2F::Scale(2,.4) * D2D1::Matrix3x2F::Translation(-12,23);
    auto collapsed=D2D1::Matrix3x2F::Scale(0,0);
    for(int kind=0;kind<12;kind++) for(int t=0;t<3;t++) for(float tolerance : {.05f,.25f,1.f}) {
        auto a=shape(f,kind), b=shape(ref,kind);
        const D2D1_MATRIX_3X2_F *tr=t==0 ? nullptr : t==1 ? &transformed : &collapsed;
        float actual=-1, expected=-1;
        auto ha=a->ComputeLength(tr,tolerance,&actual), hb=b->ComputeLength(tr,tolerance,&expected);
        // Arcs are already cubic approximations when stored by Wine.
        bool bad=ha!=hb || !close_float(actual,expected,kind==11 ? .02f : .0005f);
        if(bad) printf("length kind=%d tr=%d tol=%g hr=%08lx/%08lx length=%g/%g\n",kind,t,tolerance,ha,hb,actual,expected);
        failures+=bad; cases++;
        for(float length : {-10.f,0.f,1.f,5.f,10.f,expected*.5f,expected,expected+100.f}) for(int outputs=0;outputs<4;outputs++) {
            D2D1_POINT_2F ap={0,0},at={0,0},bp={0,0},bt={0,0};
            ha=a->ComputePointAtLength(length,tr,tolerance,outputs&1?&ap:nullptr,outputs&2?&at:nullptr);
            hb=b->ComputePointAtLength(length,tr,tolerance,outputs&1?&bp:nullptr,outputs&2?&bt:nullptr);
            float epsilon=kind==11 ? .025f : .0005f;
            bool tangent_ok=close_float(at.x,bt.x,.0005f) && close_float(at.y,bt.y,.0005f);
            if(kind==11 && (outputs&2) && std::isfinite(at.x) && std::isfinite(bt.x)) {
                // Wine stores arcs as cubics; native arcs may be flattened at
                // different subdivision points. Bound their tangent angle by
                // twice the chord/sagitta angle for the minimum curvature
                // radius, accounting for the non-uniform world transform.
                float radius=15.f*15.f/22.f;
                if(t==1) radius*=.4f*.4f/2.f;
                float angle=2.f*std::acos(1.f-std::fmin(tolerance/radius,1.f));
                tangent_ok=close_float(at.x*at.x+at.y*at.y,1.f,.0001f) &&
                           at.x*bt.x+at.y*bt.y >= std::cos(angle);
            }
            bad=ha!=hb || !close_float(ap.x,bp.x,epsilon) || !close_float(ap.y,bp.y,epsilon) || !tangent_ok;
            if(bad && failures<15) printf("point kind=%d tr=%d len=%g outputs=%d hr=%08lx/%08lx point=%g,%g/%g,%g tangent=%g,%g/%g,%g\n",kind,t,length,outputs,ha,hb,ap.x,ap.y,bp.x,bp.y,at.x,at.y,bt.x,bt.y);
            failures+=bad; cases++;
        }
        a->Release();b->Release();
    }
    printf("Reference comparisons: %d cases, %d failures\n",cases,failures);
    std::atomic<int> concurrent_failures{0}; std::vector<std::thread> workers;
    for(int thread=0;thread<8;thread++) workers.emplace_back([&]{
        for(int i=0;i<100;i++) {
            auto g=shape(f,7); float len; D2D1_POINT_2F p,t;
            if(FAILED(g->ComputeLength(nullptr,.1f,&len)) || !close_float(len,15,.0001f) ||
               FAILED(g->ComputePointAtLength(2.5f,nullptr,.1f,&p,&t)) ||
               !close_float(p.x,1.5f,.0001f) || !close_float(p.y,2,.0001f) || !close_float(t.x,.6f,.0001f) || !close_float(t.y,.8f,.0001f)) concurrent_failures++;
            g->Release();
        }
    });
    for(auto &worker : workers)worker.join();
    printf("Concurrent analytic checks: 800 cases, %d failures\n",concurrent_failures.load());
    ref->Release();f->Release();return failures || concurrent_failures.load();
}
