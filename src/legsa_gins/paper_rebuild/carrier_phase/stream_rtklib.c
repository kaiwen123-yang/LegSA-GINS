/* Causal, receiver-separated UBX decoding into the existing broadcast ABI.
 * Built with the hash-recorded external bridge and pinned RTKLIB sources.
 * No orbit equations, measurement edits, or cross-receiver page assembly. */
#include "legsa_rtklib_bridge.c"

typedef struct {
    legsa_nav_context_t nav;
    raw_t raw[2];
} legsa_stream_context_t;

void *legsa_stream_new(int week, double tow)
{
    legsa_stream_context_t *ctx=calloc(1,sizeof(*ctx));
    int i;
    if (!ctx) return NULL;
    for (i=0;i<2;i++) {
        if (!init_raw(&ctx->raw[i],STRFMT_UBX)) {
            while (i>0) free_raw(&ctx->raw[--i]);
            free(ctx); return NULL;
        }
        /* The first arrived RAWX supplies calendar context; no host date seed. */
        ctx->raw[i].time=gpst2time(week,tow);
    }
    return ctx;
}

void *legsa_stream_nav(void *handle)
{
    legsa_stream_context_t *ctx=handle;
    return ctx?&ctx->nav:NULL;
}

void legsa_stream_free(void *handle)
{
    legsa_stream_context_t *ctx=handle;
    if (!ctx) return;
    free_raw(&ctx->raw[0]); free_raw(&ctx->raw[1]);
    freenav(&ctx->nav.nav,0xFF);
    free(ctx);
}

/* Exactly one complete UBX frame per call. Return appended ephemeris index
 * plus one, zero for no CDMA ephemeris, negative only for a decoder/error. */
int legsa_stream_frame(void *handle, int receiver, const unsigned char *bytes,
                       int length, int *satellite)
{
    legsa_stream_context_t *ctx=handle;
    raw_t *raw;
    nav_t *nav;
    eph_t *grown;
    int i,status=0,sys,index;
    if (!ctx||receiver<1||receiver>2||!bytes||length<=0) return -100;
    raw=&ctx->raw[receiver-1]; nav=&ctx->nav.nav;
    for (i=0;i<length;i++) {
        int result=input_ubx(raw,bytes[i]);
        if (result) status=result;
    }
    if (status<0) return status;
    if (status!=2) return 0;
    sys=satsys(raw->ephsat,NULL);
    if (!(sys&(SYS_GPS|SYS_GAL|SYS_CMP))) return 0;
    if (nav->n==nav->nmax) {
        int capacity=nav->nmax+64;
        grown=realloc(nav->eph,sizeof(eph_t)*capacity);
        if (!grown) return -101;
        nav->eph=grown; nav->nmax=capacity;
    }
    index=raw->ephsat-1+MAXSAT*raw->ephset;
    nav->eph[nav->n++]=raw->nav.eph[index];
    *satellite=raw->ephsat;
    return nav->n;
}

/* Same selector as the existing audit ABI; links a state to its exact
 * received ephemeris record, even when both receivers decoded the same IOD. */
int legsa_stream_selected(void *handle, int week, double tow, int satellite)
{
    legsa_stream_context_t *ctx=handle;
    const eph_t *eph;
    if (!ctx) return -1;
    eph=legsa_select_eph(gpst2time(week,tow),satellite,&ctx->nav.nav);
    return eph?(int)(eph-ctx->nav.nav.eph):-1;
}
