#!/usr/bin/env python3
"""Reconstruct direct carrier position-error increments from sealed priors only."""
import argparse,csv,hashlib,json,struct
from pathlib import Path
import numpy as np


def read(p):return json.loads(Path(p).read_text())
def pin(p):return dict(path=str(p),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
def checked(j):
    assert pin(j['path'])['sha256']==j['sha256'];return Path(j['path'])
def rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def bits(t):return struct.pack('>d',float(t)).hex()
def mat(r,prefix,suffix):return np.array([[float(r[prefix+a+b+suffix]) for b in 'ned'] for a in 'ned'])
def vec(r,prefix,suffix):return np.array([float(r[prefix+a+suffix]) for a in 'ned'])
def skew(h):
    x,y,z=h;return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
def table(p,data):
    keys=list(dict.fromkeys(k for r in data for k in r))
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(data)
def stat(a):
    a=np.asarray(a,dtype=float)
    return dict(n=len(a),min=float(min(a)) if len(a) else None,median=float(np.median(a)) if len(a) else None,
                p95=float(np.quantile(a,.95)) if len(a) else None,max=float(max(a)) if len(a) else None,
                per_update_rms=float(np.sqrt(np.mean(a*a))) if len(a) else None)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--stage',type=Path,required=True);ap.add_argument('--docs',type=Path,required=True);a=ap.parse_args()
    stage=a.stage.resolve();plan=read(stage/'PLAN.json');seal=read(stage/'ALL_NATIVE_SEALED.json')
    assert seal['plan_sha256']==pin(stage/'PLAN.json')['sha256']
    lo,hi=plan['position_intervention']['interval']
    pp=next(r['carrier'] for r in plan['runs'] if r['arm']=='SDK_GAP_PARTIAL')
    fp=next(r['carrier'] for r in plan['runs'] if r['arm']=='SDK_GAP_FULL_ONLY')
    prows,frows=rows(checked(pp)),rows(checked(fp));assert len(prows)==len(frows)
    source=[]
    for i,(p,f) in enumerate(zip(prows,frows)):
        assert bits(p['measurement_time'])==bits(f['measurement_time'])
        t=float(p['measurement_time'])
        if lo<t<hi and p['valid']=='1' and f['valid']=='0':source.append(dict(source_row_zero_based=i,time=t,time_bits=bits(t)))
    assert len(source)==30
    output=[];summary={};allchecks=[];pins=[pin(stage/'PLAN.json'),pp,fp]
    for run in plan['runs']:
        native=stage/'NATIVE'/run['run_id'];result=read(native/'RESULT.json')
        assert result['status']=='COMPLETED' and result['online_reference_opens']==0
        dpath=native/'BASELINE3D_DIAGNOSTICS.csv';spath=native/'SOURCE_AWARE_WEIGHT_TRACE.csv'
        data=rows(dpath);di={}
        for r in data:
            if r['source']=='external_carrier' and r['measurement_time']:
                key=bits(r['measurement_time'])
                if key in {q['time_bits'] for q in source}:
                    assert key not in di,key
                    di[key]=r
        sa={round(float(r['time']),7):r for r in rows(spath) if r['source_id']=='dual_antenna_yaw'}
        armrows=[];checks=[]
        for q in source:
            r=di[q['time_bits']];accepted=r['accepted']=='1';available=r['prior_available']=='1'
            row=dict(arm=run['arm'],**q,attempted=int(r['attempt']),accepted=int(accepted),reason=r['reason'],prior_available=int(available))
            delta=np.zeros(3);phi_delta=np.zeros(3)
            if available:
                assert r['prior_phase']=='PRE_CURRENT_CARRIER_UPDATE'
                assert r['event_time_bits_hex']==r['prior_state_time_bits_hex']==q['time_bits']
                assert r['prior_error_chart']=='GI_LEFT_NED_PHI_POSITION_MINUS'
                h=vec(r,'h_','_m');A=skew(h);Pphi=mat(r,'prior_P_phi_phi_','_rad2');Ppphi=mat(r,'prior_P_p_phi_','_m_rad')
                Ppp=mat(r,'prior_P_p_p_','_m2');R=mat(r,'R_','');mu=vec(r,'prior_dx_phi_','_rad');mu_p=vec(r,'prior_dx_p_','_m')
                innovation=vec(r,'innovation_','_m');dz=vec(r,'dz_','_m');qa=float(r['qa_R_scale']);sa_scale=float(r['sa_R_scale'])
                S0=A@Pphi@A.T+qa*R
                c=dict(arm=run['arm'],time=q['time'],innovation_reconstruction_max_abs_m=float(max(abs(innovation-(dz-A@mu)))),
                    hard_nis_reconstruction_abs_error=abs(float(innovation@np.linalg.solve(S0,innovation))-float(r['nis_actual_innovation'])),
                    Pphi_symmetry_max_abs=float(np.max(abs(Pphi-Pphi.T))),Ppp_symmetry_max_abs=float(np.max(abs(Ppp-Ppp.T))))
                row.update(prior_mu_phi_norm_rad=float(np.linalg.norm(mu)),prior_mu_p_norm_m=float(np.linalg.norm(mu_p)),
                    P_p_phi_frobenius_m_rad=float(np.linalg.norm(Ppphi)),P_phi_phi_max_eigen_rad2=float(np.linalg.eigvalsh(Pphi)[-1]),
                    prior_horizontal_position_sigma_m=float(np.sqrt(Ppp[0,0]+Ppp[1,1])),hard_nis=float(r['nis_actual_innovation']),qa_R_scale=qa,sa_R_scale=sa_scale)
                if accepted:
                    sr=sa[round(q['time'],7)];assert abs(float(sr['time'])-q['time'])<1e-8
                    effective_R=qa*sa_scale*R
                    c['scaled_R_trace_reconstruction_abs_error']=abs(float(np.trace(effective_R))-float(sr['scaled_R_trace']))
                    # SA actually records scaled_R_trace: verify the operative scale, not configuration alone.
                    assert c['scaled_R_trace_reconstruction_abs_error']<1e-8
                    S=A@Pphi@A.T+effective_R
                    Kp=np.linalg.solve(S,(Ppphi@A.T).T).T
                    Kphi=np.linalg.solve(S,(Pphi@A.T).T).T
                    delta=Kp@innovation;phi_delta=Kphi@innovation
                    reduction=Kp@S@Kp.T
                    row.update(K_p_horizontal_frobenius=float(np.linalg.norm(Kp[:2])),
                        direct_Ppp_horizontal_trace_reduction_m2=float(reduction[0,0]+reduction[1,1]),
                        direct_Ppp_horizontal_fraction_reduction=float((reduction[0,0]+reduction[1,1])/(Ppp[0,0]+Ppp[1,1])),
                        effective_R_trace_m2=float(np.trace(effective_R)))
                checks.append(c)
            else:
                assert not accepted
            for i,axis in enumerate('ned'):
                row['actual_delta_error_p_'+axis+'_m']=float(delta[i])
                row['feedback_tangent_p_'+axis+'_m']=float(-delta[i])
                row['actual_delta_error_phi_'+axis+'_rad']=float(phi_delta[i])
            row['actual_position_increment_horizontal_norm_m']=float(np.linalg.norm(delta[:2]))
            row['actual_position_increment_3d_norm_m']=float(np.linalg.norm(delta))
            row['actual_attitude_increment_norm_rad']=float(np.linalg.norm(phi_delta))
            armrows.append(row);output.append(row)
        available=[r for r in armrows if r['prior_available']];acc=[r for r in armrows if r['accepted']]
        summary[run['arm']]=dict(source_rows=30,attempts=sum(r['attempted'] for r in armrows),accepted=len(acc),
            actual_zero_updates=sum(not r['accepted'] for r in armrows),prior_rows=len(available),
            nonzero_phi_error_mean_rows=sum(r['prior_mu_phi_norm_rad']!=0 for r in available),
            nonzero_position_error_mean_rows=sum(r['prior_mu_p_norm_m']!=0 for r in available),
            actual_horizontal_increment_all30_m=stat([r['actual_position_increment_horizontal_norm_m'] for r in armrows]),
            actual_horizontal_increment_accepted_m=stat([r['actual_position_increment_horizontal_norm_m'] for r in acc]),
            P_p_phi_frobenius_all_available_m_rad=stat([r['P_p_phi_frobenius_m_rad'] for r in available]),
            K_p_horizontal_frobenius_accepted=stat([r['K_p_horizontal_frobenius'] for r in acc]),
            direct_Ppp_horizontal_fraction_reduction_accepted=stat([r['direct_Ppp_horizontal_fraction_reduction'] for r in acc]),
            feedback_tangent_mean_NED_m=np.mean([[r['feedback_tangent_p_'+d+'_m'] for d in 'ned'] for r in armrows],axis=0).tolist(),
            no_sum_as_net_navigation_effect=True)
        allchecks.extend(checks);pins.extend([pin(dpath),pin(spath),pin(native/'RESULT.json')])
    paired=[]
    for q in source:
        u=next(r for r in output if r['arm']=='SDK_GAP_PARTIAL' and r['time_bits']==q['time_bits'])
        v=next(r for r in output if r['arm']=='FOOT_GAP_PARTIAL' and r['time_bits']==q['time_bits'])
        paired.append(dict(**q,SDK_accepted=u['accepted'],FOOT_accepted=v['accepted'],
            SDK_position_increment_H_m=u['actual_position_increment_horizontal_norm_m'],FOOT_position_increment_H_m=v['actual_position_increment_horizontal_norm_m'],
            SDK_cross_norm_m_rad=u['P_p_phi_frobenius_m_rad'],FOOT_cross_norm_m_rad=v['P_p_phi_frobenius_m_rad']))
    out=stage/'CARRIER_CROSS_READOUT';out.mkdir(exist_ok=False)
    table(out/'PER_SOURCE.csv',output);table(out/'PAIRED_SOURCE.csv',paired);table(out/'RECONSTRUCTION_CHECKS.csv',allchecks)
    src=Path(__file__).resolve().parents[3]/'cpp/legsa_v23_port_core/src'
    report=dict(schema='carrier_direct_position_increment.v1',plan=pin(stage/'PLAN.json'),runner=pin(__file__),inputs=pins,
        code_identity=[pin(src/x) for x in ['baseline3d.cpp','kf_gins/gi_engine.cpp','factors/pose_clone.cpp']],summary=summary,
        reconstruction_maxima={k:max(c.get(k,0) for c in allchecks) for k in ['innovation_reconstruction_max_abs_m','hard_nis_reconstruction_abs_error','scaled_R_trace_reconstruction_abs_error']},
        formula='A=skew(h); S=A P_phi_phi A^T + qa_scale*sa_scale*R; delta_mu_p=P_p_phi A^T S^-1 innovation, only when accepted; position feedback NED tangent=-delta_mu_p',
        scope='Exact current linear update from recorded marginal blocks up to serialized/numerical precision; not exact nonlinear posterior or accumulated/final position gain. Current H has zero position/clone columns and fixed nominal-position frame.',
        no_velocity_increment_claim='P_v_phi not recorded; no exact velocity increment reconstructed',
        NAV_reads=0,reference_reads=0,evaluator_calls=0,native_calls=0)
    (out/'SUMMARY.json').write_text(json.dumps(report,indent=2)+'\n')
    a.docs.mkdir(exist_ok=True,parents=True);table(a.docs/'POSITION_PRODUCT_GAP_CARRIER_CROSS.csv',output)
    text=['# 位置产品缺口：载波到共同位置的直接交叉更新','',
          '仅读取已封存原生日志，完整保留源定义的30个gap partial和四臂。没有读取NAV/reference，没有运行求解器或评价器。',
          '', '## 当前实现中的精确线性更新','',
          'external模型的H只有Hφ=[h]×，位置、速度、clone及公共杆臂列均为0。观测与R在nominal位置旋到NED，代码未加入该坐标旋转对位置误差的导数。以下是实际实现的重建，不把该省略补成另一物理模型。',
          '', '`S = [h]× Pφφ [h]×ᵀ + (qa_scale · sa_scale) R`',
          '', '`δμp = Ppφ [h]×ᵀ S⁻¹ innovation`。innovation已是dz−Hμ；不能再减一次。拒绝/未尝试实际增量为0。pose clone联合更新使用同一公式；H的其余列为0，故所记录当前边缘足够，不用补造clone交叉块。',
          '', 'GIEngine位置反馈为p←p−DRi(p)μp；对应NED反馈切向量为−δμp。这里没有P_vφ，因此不声称重建精确速度增量。',
          '', '| arm | 源分母 | 尝试/接受 | 单次位置H修正 median / p95 / max，含实际0（mm） |','|---|---:|---:|---:|']
    for arm,s in summary.items():
        h=s['actual_horizontal_increment_all30_m'];text.append(f"| {arm} | 30 | {s['attempts']}/{s['accepted']} | {1000*h['median']:.6f} / {1000*h['p95']:.6f} / {1000*h['max']:.6f} |")
    text+=['','## 限定','',
           '上述每观测修正不等于最终p差，更不等于真实误差或相对参考RMSE收益。不能把逐次RMS求和当累计位置误差；后续SDK、foot、PVT velocity、Doppler、恢复position和传播还会改变同一状态。',
           'SDK/FOOT对照的cross差属于两种完整历史和SDK替代政策的结果，不单独证明foot带来独立信息；Ppp收缩也不是精度认证。完整所有30行、未尝试/拒绝及conditional mean统计均保留。',
           '',f"机器结果：`{out/'SUMMARY.json'}`；完整源行：`POSITION_PRODUCT_GAP_CARRIER_CROSS.csv`。",
           '公式重建与实际hard NIS、scaled R trace的数值核对见RECONSTRUCTION_CHECKS.csv，仅核对已保存量，不新增测试或native。','']
    (a.docs/'POSITION_PRODUCT_GAP_CARRIER_CROSS.md').write_text('\n'.join(text))
    print(json.dumps(dict(output=str(out),summary=summary,reconstruction_maxima=report['reconstruction_maxima']),indent=2))


if __name__=='__main__':main()
