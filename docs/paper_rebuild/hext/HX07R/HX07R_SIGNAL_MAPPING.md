# HX-07-R 信号与频率索引只读映射

RTKLIB 180043ee24b6d2b168f98b64be15f69d50046b1a；未加载动态库或运行程序。实际信号来自已 pin DG01R_RINEX_CROSSCHECK.csv 的 system/signal 列。配置字符串 pos1-frequency=l1+l2 保持原字节；此运行使用双频槽 0/1，对 Galileo 是 E1/E5b，不是 E1/E5a。映射表不表示卫星实际参与解算，实际使用另据 $SAT 的 vsat。

| system | signal | code2idx | $SAT frq |
|---|---|---:|---:|
| C | 2I | 0 | 1 |
| C | 7I | 1 | 2 |
| E | 1C | 0 | 1 |
| E | 7Q | 1 | 2 |
| G | 1C | 0 | 1 |
| G | 2L | 1 | 2 |
| G | 2S | 1 | 2 |
| J | 1C | 0 | 1 |
| J | 2L | 1 | 2 |
| J | 2S | 1 | 2 |
| R | 1C | 0 | 1 |
| R | 2C | 1 | 2 |
| S | 1C | 0 | 1 |

`<RTKLIB>/src/rtkcmn.c` L599–L609:

```text
599: static int code2freq_GPS(uint8_t code, double *freq)
600: {
601:     char *obs=code2obs(code);
602:
603:     switch (obs[0]) {
604:         case '1': *freq=FREQ1; return 0; /* L1 */
605:         case '2': *freq=FREQ2; return 1; /* L2 */
606:         case '5': *freq=FREQ5; return 2; /* L5 */
607:     }
608:     return -1;
609: }
```

`<RTKLIB>/src/rtkcmn.c` L627–L652:

```text
627: static int code2freq_GAL(uint8_t code, double *freq)
628: {
629:     char *obs=code2obs(code);
630:
631:     switch (obs[0]) {
632:         case '1': *freq=FREQ1; return 0; /* E1 */
633:         case '7': *freq=FREQ7; return 1; /* E5b */
634:         case '5': *freq=FREQ5; return 2; /* E5a */
635:         case '6': *freq=FREQ6; return 3; /* E6 */
636:         case '8': *freq=FREQ8; return 4; /* E5ab */
637:     }
638:     return -1;
639: }
640: /* QZSS obs code to frequency ------------------------------------------------*/
641: static int code2freq_QZS(uint8_t code, double *freq)
642: {
643:     char *obs=code2obs(code);
644:
645:     switch (obs[0]) {
646:         case '1': *freq=FREQ1; return 0; /* L1 */
647:         case '2': *freq=FREQ2; return 1; /* L2 */
648:         case '5': *freq=FREQ5; return 2; /* L5 */
649:         case '6': *freq=FREQ6; return 3; /* L6 */
650:     }
651:     return -1;
652: }
```

`<RTKLIB>/src/rtkcmn.c` L665–L678:

```text
665: static int code2freq_BDS(uint8_t code, double *freq)
666: {
667:     char *obs=code2obs(code);
668:
669:     switch (obs[0]) {
670:         case '1': *freq=FREQ1;     return 0; /* B1C */
671:         case '2': *freq=FREQ1_CMP; return 0; /* B1I */
672:         case '7': *freq=FREQ2_CMP; return 1; /* B2I/B2b */
673:         case '5': *freq=FREQ5;     return 2; /* B2a */
674:         case '6': *freq=FREQ3_CMP; return 3; /* B3 */
675:         case '8': *freq=FREQ8;     return 4; /* B2ab */
676:     }
677:     return -1;
678: }
```

`<RTKLIB>/src/rtkcmn.c` L690–L719:

```text
690: /* system and obs code to frequency index --------------------------------------
691: * convert system and obs code to frequency index
692: * args   : int    sys       I   satellite system (SYS_???)
693: *          uint8_t code     I   obs code (CODE_???)
694: * return : frequency index (-1: error)
695: *                       0     1     2     3     4
696: *           --------------------------------------
697: *            GPS       L1    L2    L5     -     -
698: *            GLONASS   G1    G2    G3     -     -  (G1=G1,G1a,G2=G2,G2a)
699: *            Galileo   E1    E5b   E5a   E6   E5ab
700: *            QZSS      L1    L2    L5    L6     -
701: *            SBAS      L1     -    L5     -     -
702: *            BDS       B1    B2    B2a   B3   B2ab (B1=B1I,B1C,B2=B2I,B2b)
703: *            NavIC     L5     S     -     -     -
704: *-----------------------------------------------------------------------------*/
705: extern int code2idx(int sys, uint8_t code)
706: {
707:     double freq;
708:
709:     switch (sys) {
710:         case SYS_GPS: return code2freq_GPS(code,&freq);
711:         case SYS_GLO: return code2freq_GLO(code,0,&freq);
712:         case SYS_GAL: return code2freq_GAL(code,&freq);
713:         case SYS_QZS: return code2freq_QZS(code,&freq);
714:         case SYS_SBS: return code2freq_SBS(code,&freq);
715:         case SYS_CMP: return code2freq_BDS(code,&freq);
716:         case SYS_IRN: return code2freq_IRN(code,&freq);
717:     }
718:     return -1;
719: }
```

`<RTKLIB>/src/options.c` L44–L48:

```text
44: #define SWTOPT  "0:off,1:on"
45: #define MODOPT  "0:single,1:dgps,2:kinematic,3:static,4:movingbase,5:fixed,6:ppp-kine,7:ppp-static,8:ppp-fixed"
46: #define FRQOPT  "1:l1,2:l1+2,3:l1+2+3,4:l1+2+3+4,5:l1+2+3+4+5"
47: #define TYPOPT  "0:forward,1:backward,2:combined"
48: #define IONOPT  "0:off,1:brdc,2:sbas,3:dual-freq,4:est-stec,5:ionex-tec,6:qzs-brdc"
```

`<RTKLIB>/src/options.c` L65–L69:

```text
65:
66: EXPORT opt_t sysopts[]={
67:     {"pos1-posmode",    3,  (void *)&prcopt_.mode,       MODOPT },
68:     {"pos1-frequency",  3,  (void *)&prcopt_.nf,         FRQOPT },
69:     {"pos1-soltype",    3,  (void *)&prcopt_.soltype,    TYPOPT },
```

`<RTKLIB>/src/rtkpos.c` L73–L78:

```text
73: #define TTOL_MOVEB  (1.0+2*DTTOL)
74:                              /* time sync tolerance for moving-baseline (s) */
75:
76: /* number of parameters (pos,ionos,tropos,hw-bias,phase-bias,real,estimated) */
77: #define NF(opt)     ((opt)->ionoopt==IONOOPT_IFLC?1:(opt)->nf)
78: #define NP(opt)     ((opt)->dynamics==0?3:9)
```

`<RTKLIB>/src/rtkpos.c` L331–L348:

```text
331:     if (rtk->sol.stat==SOLQ_NONE||statlevel<=1) return;
332:
333:     tow=time2gpst(rtk->sol.time,&week);
334:     nfreq=rtk->opt.mode>=PMODE_DGPS?nf:1;
335:
336:     /* write residuals and status */
337:     for (i=0;i<MAXSAT;i++) {
338:         ssat=rtk->ssat+i;
339:         if (!ssat->vs) continue;
340:         satno2id(i+1,id);
341:         for (j=0;j<nfreq;j++) {
342:             fprintf(fp_stat,"$SAT,%d,%.3f,%s,%d,%.1f,%.1f,%.4f,%.4f,%d,%.1f,%d,%d,%d,%d,%d,%d\n",
343:                     week,tow,id,j+1,ssat->azel[0]*R2D,ssat->azel[1]*R2D,
344:                     ssat->resp[j],ssat->resc[j],ssat->vsat[j],
345:                     ssat->snr[j]*SNR_UNIT,ssat->fix[j],ssat->slip[j]&3,
346:                     ssat->lock[j],ssat->outc[j],ssat->slipc[j],ssat->rejc[j]);
347:         }
348:     }
```

R/S 作为数据中实际出现的额外信号登记，四变体 navsys 均不启用它们。G/J 的 2S 也出现，均为索引 1。$SAT 字段依次为记录名、week、tow、sat、frq、az、el、resp、resc、vsat、snr、fix、slip、lock、outc、slipc、rejc（17 字段）。
