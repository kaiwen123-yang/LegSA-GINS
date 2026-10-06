/* Minimal read-only extension to the existing, pinned RTKLIB bridge.
 * RTKLIB functions: BSD-2-Clause, T. Takasu. No change to the frozen libraries.
 * The context layout and build macros must match legsa_rtklib_bridge.c.
 */
#include <math.h>
#include "rtklib.h"
typedef struct { obs_t obs; nav_t nav; sta_t sta; } context_t;

int fgo_corrections(void *handle, int week, double tow, int sat,
                    const double *rr, const double *azel, double frequency,
                    double *out) {
    context_t *ctx=(context_t *)handle;
    gtime_t t=gpst2time(week,tow);
    double pos[3], ion, vi, trop, vt, best=1e99;
    int index=-1, sys=satsys(sat,0), i;
    if (!ctx || !(frequency>0) || (sys!=SYS_GPS && sys!=SYS_CMP)) return 0;
    ecef2pos(rr,pos);
    if (!ionocorr(t,&ctx->nav,sat,pos,azel,IONOOPT_BRDC,&ion,&vi) ||
        !tropcorr(t,&ctx->nav,pos,azel,TROPOPT_SAAS,&trop,&vt)) return 0;
    for (i=0;i<ctx->nav.n;i++) {
        double age=fabs(timediff(t,ctx->nav.eph[i].toe));
        if (ctx->nav.eph[i].sat==sat && age<=best) { best=age; index=i; }
    }
    if (index<0 || best>(sys==SYS_GPS?MAXDTOE:MAXDTOE_CMP)+1.0) return 0;
    /* GPS L1 C/A and BeiDou B1I have the same selected TGD index zero.
       No dual-frequency or B1C observations cross this extension. */
    out[0]=ion*FREQ1*FREQ1/(frequency*frequency);
    out[1]=trop;
    out[2]=CLIGHT*ctx->nav.eph[index].tgd[0];
    out[3]=sys==SYS_GPS?ctx->nav.cbias[sat-1][1]:0.0;
    out[4]=vi; out[5]=vt;
    return isfinite(out[0]) && isfinite(out[1]) && isfinite(out[2]);
}
