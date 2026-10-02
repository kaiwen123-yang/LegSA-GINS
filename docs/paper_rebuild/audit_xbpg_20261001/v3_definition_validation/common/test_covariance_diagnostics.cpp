#include "covariance_diagnostics.hpp"
#include <cstring>
#include <iostream>
#include <limits>
using namespace legsa_v23_port_core;
int main(){
  int checked=0,failed=0;
  auto run=[&](const std::string& name,Matrix p,const std::string& expected){
    auto before=p.data;const auto r=candidate_diagnostics::inspect(p);
    const bool unchanged=before.size()==p.data.size()&&std::memcmp(before.data(),p.data.data(),before.size()*sizeof(double))==0;
    const bool pass=r.status==expected&&unchanged;
    std::cout<<mechanism_observer::Json().add("test",name).add("passed",pass).add("source_unchanged",unchanged)
      .add("expected",expected).raw("actual",r.json().str()).str()<<'\n';++checked;if(!pass)++failed;
  };
  const std::string ok="POSITIVE_DEFINITE_WITHIN_FIXED_NUMERIC_DIAGNOSTIC";
  Matrix identity(21,21,0.0);for(std::size_t i=0;i<21;++i)identity(i,i)=1;
  run("identity_full21",identity,ok);
  Matrix scaled=identity;for(std::size_t i=0;i<21;++i)scaled(i,i)=std::pow(10.0,-200.0+20.0*i);
  run("large_scale_range_full21",scaled,ok);
  Matrix corr=identity;corr(0,1)=corr(1,0)=0.7;run("correlated_full21",corr,ok);
  Matrix bad=identity;bad(0,1)=std::numeric_limits<double>::quiet_NaN();run("offdiagonal_nan",bad,"NONFINITE_MATRIX");
  bad=identity;bad(4,4)=std::numeric_limits<double>::infinity();run("diagonal_infinity",bad,"NONFINITE_MATRIX");
  bad=identity;bad(4,4)=0;run("zero_diagonal",bad,"NONPOSITIVE_DIAGONAL");
  bad=identity;bad(0,1)=0.1;run("asymmetric",bad,"ASYMMETRIC");
  bad=identity;bad(0,1)=1e-11;run("asymmetry_within_fixed_tolerance",bad,ok);
  bad=identity;bad(0,1)=bad(1,0)=2;run("positive_diagonal_indefinite",bad,"CHOLESKY_NEGATIVE_PIVOT_RISK");
  bad=identity;bad(0,1)=bad(1,0)=1;run("rank_deficient_positive_diagonal",bad,"NEAR_SINGULAR_NUMERICALLY_UNRESOLVED");
  bad=identity;bad(0,1)=bad(1,0)=1-1e-13;run("small_positive_pivot_unresolved",bad,"NEAR_SINGULAR_NUMERICALLY_UNRESOLVED");
  run("invalid_shape",Matrix(2,3,1),"INVALID_SHAPE");
  std::cout<<mechanism_observer::Json().add("tests",checked).add("failed",failed).add("synthetic_data_used",true)
    .add("semisynthetic_data_used",false).add("real_native_calls",0).str()<<'\n';return failed?1:0;
}
