"""Case inventory and emitted C++ bodies for rational/complex expansion roots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArithmeticCase:
    task_id: str
    title: str
    domain: str
    mechanism: str
    declaration: str
    signature: str
    core: str
    negative_core: str
    visible_test: str
    hidden_test: str
    valid_behavior: str
    invalid_behavior: str
    ordering_behavior: str
    negative_name: str
    extra_header: str = ""
    numeric_policy: str = ""

    @property
    def class_name(self) -> str:
        return "".join(part.title() for part in self.task_id.split("-"))

    @property
    def method_name(self) -> str:
        return self.declaration.split("(", 1)[0].split()[-1]


RATIONAL_SUPPORT = r'''
namespace {
using R = Rational;
bool add_ll(long long a,long long b,long long& out){return !__builtin_add_overflow(a,b,&out);}
bool sub_ll(long long a,long long b,long long& out){return !__builtin_sub_overflow(a,b,&out);}
bool mul_ll(long long a,long long b,long long& out){return !__builtin_mul_overflow(a,b,&out);}
std::optional<R> normalized(R v){
  if(v.denominator==0||v.numerator==std::numeric_limits<long long>::min()||v.denominator==std::numeric_limits<long long>::min())return std::nullopt;
  if(v.denominator<0){v.denominator=-v.denominator;v.numerator=-v.numerator;}
  long long g=std::gcd(std::llabs(v.numerator),v.denominator);if(g==0)g=1;
  v.numerator/=g;v.denominator/=g;return v;
}
std::optional<R> add_r(R a,R b){auto x=normalized(a),y=normalized(b);if(!x||!y)return std::nullopt;long long p,q,r,d;if(!mul_ll(x->numerator,y->denominator,p)||!mul_ll(y->numerator,x->denominator,q)||!add_ll(p,q,r)||!mul_ll(x->denominator,y->denominator,d))return std::nullopt;return normalized({r,d});}
std::optional<R> sub_r(R a,R b){if(b.numerator==std::numeric_limits<long long>::min())return std::nullopt;b.numerator=-b.numerator;return add_r(a,b);}
std::optional<R> mul_r(R a,R b){auto x=normalized(a),y=normalized(b);if(!x||!y)return std::nullopt;long long n,d;if(!mul_ll(x->numerator,y->numerator,n)||!mul_ll(x->denominator,y->denominator,d))return std::nullopt;return normalized({n,d});}
std::optional<R> div_r(R a,R b){auto y=normalized(b);if(!y||y->numerator==0)return std::nullopt;return mul_r(a,{y->denominator,y->numerator});}
std::optional<int> cmp_r(R a,R b){auto x=normalized(a),y=normalized(b);if(!x||!y)return std::nullopt;long long p,q;if(!mul_ll(x->numerator,y->denominator,p)||!mul_ll(y->numerator,x->denominator,q))return std::nullopt;return p<q?-1:(p>q?1:0);}
std::optional<R> abs_r(R value){auto n=normalized(value);if(!n||n->numerator==std::numeric_limits<long long>::min())return std::nullopt;if(n->numerator<0)n->numerator=-n->numerator;return n;}
bool equal_r(R a,R b){auto c=cmp_r(a,b);return c&&*c==0;}
}  // namespace
'''


def _rational_cases() -> tuple[ArithmeticCase, ...]:
    rows: list[ArithmeticCase] = []
    add = rows.append
    add(ArithmeticCase(
        "rational-continued-fraction-convergents", "Continued-fraction convergents", "rational",
        "second-order numerator/denominator recurrence emitting every convergent",
        "std::optional<std::vector<Rational>> convergents(const std::vector<long long>& terms) const",
        "std::optional<std::vector<Rational>> {cls}::convergents(const std::vector<long long>& terms) const",
        r'''if(terms.empty())return std::nullopt;long long p2=0,p1=1,q2=1,q1=0;std::vector<R> out;for(std::size_t i=0;i<terms.size();++i){if(i>0&&terms[i]<=0)return std::nullopt;long long ap,aq,p,q;if(!mul_ll(terms[i],p1,ap)||!mul_ll(terms[i],q1,aq)||!add_ll(ap,p2,p)||!add_ll(aq,q2,q))return std::nullopt;auto value=normalized({p,q});if(!value)return std::nullopt;out.push_back(*value);p2=p1;p1=p;q2=q1;q1=q;}return out;''',
        r'''if(terms.empty())return std::nullopt;long long p0=0,p1=1,q0=1,q1=0;for(long long a:terms){long long p=a*p1+p0,q=a*q1+q0;p0=p1;p1=p;q0=q1;q1=q;}auto last=normalized({p1,q1});if(!last)return std::nullopt;return std::vector<R>{*last};''',
        "auto r=RationalContinuedFractionConvergents{}.convergents({1,2,2});return !r||r->size()!=3||!same((*r)[0],{1,1})||!same((*r)[2],{7,5});",
        "auto x=RationalContinuedFractionConvergents{};return x.convergents({})||x.convergents({1,0})||!x.convergents({-2,3,4});",
        "Emit the complete recurrence sequence for a finite simple continued fraction.",
        "Reject an empty list, a nonpositive term after the first, or checked overflow.",
        "Preserve coefficient order and include the first and final convergents.",
        "final-convergent-only"))
    add(ArithmeticCase(
        "rational-stern-brocot-locate", "Stern-Brocot location", "rational",
        "bounded exact mediant search between sentinel fractions",
        "std::optional<std::string> locate(Rational target, std::size_t max_steps) const",
        "std::optional<std::string> {cls}::locate(Rational target, std::size_t max_steps) const",
        r'''auto t=normalized(target);if(!t||t->numerator<=0)return std::nullopt;if(equal_r(*t,{1,1}))return std::string{};long long ln=0,ld=1,rn=1,rd=0;std::string path;for(std::size_t step=0;step<max_steps;++step){long long mn,md;if(!add_ll(ln,rn,mn)||!add_ll(ld,rd,md))return std::nullopt;auto c=cmp_r(*t,{mn,md});if(!c)return std::nullopt;if(*c==0)return path;if(*c<0){path.push_back('L');rn=mn;rd=md;}else{path.push_back('R');ln=mn;ld=md;}}return std::nullopt;''',
        r'''auto t=normalized(target);if(!t||t->numerator<=0)return std::nullopt;if(equal_r(*t,{1,1}))return std::string{};std::string out;char direction=t->numerator>t->denominator?'R':'L';for(std::size_t i=0;i<max_steps&&i<2;++i)out.push_back(direction);return out;''',
        "auto r=RationalSternBrocotLocate{}.locate({3,2},8);return !r||*r!=\"RL\";",
        "auto x=RationalSternBrocotLocate{};return !x.locate({1,1},0)||x.locate({0,1},4)||x.locate({5,3},1);",
        "Locate a positive reduced rational by exact comparison with successive mediants.",
        "Reject nonpositive or invalid targets, overflow, and paths longer than the supplied bound.",
        "Append one L/R decision per search step; the root 1/1 has the empty path.",
        "single-direction-path"))
    add(ArithmeticCase(
        "rational-farey-neighbor-gap", "Farey neighbor gap", "rational",
        "Farey-order adjacency certificate using an exact cross determinant",
        "std::optional<Rational> neighbor_gap(Rational left, Rational right, long long order) const",
        "std::optional<Rational> {cls}::neighbor_gap(Rational left, Rational right, long long order) const",
        r'''auto l=normalized(left),r=normalized(right);if(!l||!r||order<1||l->denominator>order||r->denominator>order)return std::nullopt;auto c=cmp_r(*l,*r);if(!c||*c>=0)return std::nullopt;long long p,q,det,denominator_sum;if(!mul_ll(r->numerator,l->denominator,p)||!mul_ll(l->numerator,r->denominator,q)||!sub_ll(p,q,det)||!add_ll(l->denominator,r->denominator,denominator_sum)||det!=1||denominator_sum<=order)return std::nullopt;return sub_r(*r,*l);''',
        r'''auto l=normalized(left),r=normalized(right);if(!l||!r||order<1)return std::nullopt;auto c=cmp_r(*l,*r);if(!c||*c>=0)return std::nullopt;return sub_r(*r,*l);''',
        "auto r=RationalFareyNeighborGap{}.neighbor_gap({1,3},{2,5},5);return !r||!same(*r,{1,15});",
        "auto x=RationalFareyNeighborGap{};return x.neighbor_gap({1,3},{1,2},5)||x.neighbor_gap({1,3},{2,5},4)||x.neighbor_gap({1,2},{1,3},5)||x.neighbor_gap({1,4},{2,5},5);",
        "Certify adjacent reduced fractions in a requested Farey order and return their exact gap.",
        "Reject invalid order, out-of-order values, excessive denominators, determinant other than one, or a denominator sum at most the requested order.",
        "The left term must strictly precede the right; no inputs are mutated.",
        "ordering-only-neighbor"))
    add(ArithmeticCase(
        "rational-egyptian-decomposition", "Egyptian fraction decomposition", "rational",
        "greedy ceiling reciprocal subtraction into increasing unit denominators",
        "std::optional<std::vector<long long>> decompose(Rational value, std::size_t max_terms) const",
        "std::optional<std::vector<long long>> {cls}::decompose(Rational value, std::size_t max_terms) const",
        r'''auto remaining=normalized(value);if(!remaining)return std::nullopt;auto low=cmp_r(*remaining,{0,1}),high=cmp_r(*remaining,{1,1});if(!low||!high||*low<=0||*high>0)return std::nullopt;std::vector<long long> out;while(remaining->numerator!=0){if(out.size()>=max_terms)return std::nullopt;long long d=remaining->denominator/remaining->numerator+(remaining->denominator%remaining->numerator!=0);out.push_back(d);auto next=sub_r(*remaining,{1,d});if(!next)return std::nullopt;remaining=next;}return out;''',
        r'''auto v=normalized(value);if(!v||v->numerator<=0||max_terms==0)return std::nullopt;long long d=v->denominator/v->numerator+(v->denominator%v->numerator!=0);return std::vector<long long>{d};''',
        "auto r=RationalEgyptianDecomposition{}.decompose({5,6},4);return !r||*r!=std::vector<long long>({2,3});",
        "auto x=RationalEgyptianDecomposition{};auto one=x.decompose({1,1},1);return !one||*one!=std::vector<long long>({1})||x.decompose({0,1},2)||x.decompose({5,6},1);",
        "Repeatedly choose the smallest unit fraction not exceeding the positive proper value.",
        "Reject values outside (0,1], invalid rationals, overflow, or exhaustion of max_terms.",
        "Unit denominators are emitted in greedy order and are strictly increasing after the first subtraction.",
        "first-unit-only"))
    add(ArithmeticCase(
        "rational-bounded-approximation", "Bounded rational approximation", "rational",
        "exhaustive denominator search with exact error and stable tie comparison",
        "std::optional<Rational> approximate(Rational target, long long max_denominator) const",
        "std::optional<Rational> {cls}::approximate(Rational target, long long max_denominator) const",
        r'''auto t=normalized(target);if(!t||max_denominator<1)return std::nullopt;std::optional<R> best,error;for(long long d=1;d<=max_denominator;++d){long long scaled;if(!mul_ll(t->numerator,d,scaled))return std::nullopt;long long q=scaled/t->denominator;long long choices[2]={q,q+(scaled>=0?1:-1)};for(long long n:choices){auto cand=normalized({n,d});if(!cand)return std::nullopt;auto delta=sub_r(*t,*cand);if(!delta)return std::nullopt;auto e=abs_r(*delta);if(!e)return std::nullopt;auto c=error?cmp_r(*e,*error):std::optional<int>(-1);if(!c)return std::nullopt;if(!best||*c<0||(*c==0&&(cand->denominator<best->denominator||(cand->denominator==best->denominator&&cand->numerator<best->numerator)))){best=cand;error=e;}}}return best;''',
        r'''auto t=normalized(target);if(!t||max_denominator<1)return std::nullopt;long long scaled;if(!mul_ll(t->numerator,max_denominator,scaled))return std::nullopt;return normalized({scaled/t->denominator,max_denominator});''',
        "auto r=RationalBoundedApproximation{}.approximate({7,20},3);return !r||!same(*r,{1,3});",
        "auto x=RationalBoundedApproximation{};auto r=x.approximate({-7,20},3);auto exact=x.approximate({1,2},3);return !r||!same(*r,{-1,3})||!exact||!same(*exact,{1,2})||x.approximate({1,2},0);",
        "Search every allowed denominator and compare absolute errors without floating conversion.",
        "Reject an invalid target, a nonpositive bound, or checked overflow.",
        "Error ties choose the smaller denominator, then the smaller numerator.",
        "fixed-denominator-rounding"))
    add(ArithmeticCase(
        "rational-polynomial-horner", "Rational polynomial evaluation", "rational",
        "exact highest-degree-first Horner multiplication/addition fold",
        "std::optional<Rational> evaluate(const std::vector<Rational>& coefficients, Rational x) const",
        "std::optional<Rational> {cls}::evaluate(const std::vector<Rational>& coefficients, Rational x) const",
        r'''auto point=normalized(x);if(!point||coefficients.empty())return std::nullopt;R acc{0,1};for(R coefficient:coefficients){auto product=mul_r(acc,*point);if(!product)return std::nullopt;auto sum=add_r(*product,coefficient);if(!sum)return std::nullopt;acc=*sum;}return acc;''',
        r'''static_cast<void>(x);if(coefficients.empty())return std::nullopt;R acc{0,1};for(R coefficient:coefficients){auto sum=add_r(acc,coefficient);if(!sum)return std::nullopt;acc=*sum;}return acc;''',
        "auto r=RationalPolynomialHorner{}.evaluate({{1,2},{-1,1},{1,3}},{2,1});return !r||!same(*r,{1,3});",
        "auto x=RationalPolynomialHorner{};auto r=x.evaluate({{0,1},{2,3}},{9,5});return !r||!same(*r,{2,3})||x.evaluate({}, {1,1});",
        "Evaluate a rational-coefficient polynomial by an exact Horner fold.",
        "Reject empty coefficients, invalid rationals, or any overflowing intermediate.",
        "Coefficients are consumed from highest degree to constant; a leading zero is meaningful input.",
        "coefficient-sum"))
    add(ArithmeticCase(
        "rational-lagrange-interpolation", "Rational Lagrange interpolation", "rational",
        "exact product-basis interpolation over distinct rational abscissas",
        "std::optional<Rational> interpolate(const std::vector<RationalPoint>& samples, Rational x) const",
        "std::optional<Rational> {cls}::interpolate(const std::vector<RationalPoint>& samples, Rational x) const",
        r'''auto point=normalized(x);if(!point||samples.empty())return std::nullopt;R total{0,1};for(std::size_t i=0;i<samples.size();++i){auto xi=normalized(samples[i].x),yi=normalized(samples[i].y);if(!xi||!yi)return std::nullopt;R basis{1,1};for(std::size_t j=0;j<samples.size();++j){if(i==j)continue;auto xj=normalized(samples[j].x);if(!xj)return std::nullopt;auto denominator=sub_r(*xi,*xj),numerator=sub_r(*point,*xj);if(!denominator||!numerator||denominator->numerator==0)return std::nullopt;auto factor=div_r(*numerator,*denominator);if(!factor)return std::nullopt;auto next=mul_r(basis,*factor);if(!next)return std::nullopt;basis=*next;}auto term=mul_r(*yi,basis);if(!term)return std::nullopt;auto next=add_r(total,*term);if(!next)return std::nullopt;total=*next;}return total;''',
        r'''auto point=normalized(x);if(!point||samples.empty())return std::nullopt;std::size_t best=0;for(std::size_t i=1;i<samples.size();++i){auto a=abs_r(*sub_r(samples[i].x,*point)),b=abs_r(*sub_r(samples[best].x,*point));if(a&&b&&cmp_r(*a,*b)&&*cmp_r(*a,*b)<0)best=i;}return normalized(samples[best].y);''',
        "auto r=RationalLagrangeInterpolation{}.interpolate({{{0,1},{1,1}},{{1,1},{3,1}},{{2,1},{7,1}}},{3,1});return !r||!same(*r,{13,1});",
        "auto x=RationalLagrangeInterpolation{};auto exact=x.interpolate({{{1,2},{4,3}},{{3,2},{7,3}}},{1,2});return !exact||!same(*exact,{4,3})||x.interpolate({{{1,1},{2,1}},{{1,1},{3,1}}},{2,1});",
        "Accumulate exact Lagrange basis products for distinct rational sample coordinates.",
        "Reject empty samples, duplicate x coordinates, invalid values, or overflow.",
        "Sample order affects evaluation order but not the exact result; an exact x match returns that y.",
        "nearest-sample", "struct RationalPoint { Rational x; Rational y; };"))
    add(ArithmeticCase(
        "rational-linear-system", "Rational linear system", "rational",
        "pivoted exact Gauss-Jordan elimination",
        "std::optional<std::vector<Rational>> solve(std::vector<std::vector<Rational>> matrix, std::vector<Rational> rhs) const",
        "std::optional<std::vector<Rational>> {cls}::solve(std::vector<std::vector<Rational>> matrix, std::vector<Rational> rhs) const",
        r'''std::size_t n=matrix.size();if(n==0||rhs.size()!=n)return std::nullopt;for(const auto& row:matrix)if(row.size()!=n)return std::nullopt;for(std::size_t col=0;col<n;++col){std::size_t pivot=col;while(pivot<n){auto v=normalized(matrix[pivot][col]);if(!v)return std::nullopt;if(v->numerator!=0){break;}++pivot;}if(pivot==n)return std::nullopt;if(pivot!=col){std::swap(matrix[pivot],matrix[col]);std::swap(rhs[pivot],rhs[col]);}R p=matrix[col][col];for(std::size_t j=0;j<n;++j){auto v=div_r(matrix[col][j],p);if(!v)return std::nullopt;matrix[col][j]=*v;}auto rv=div_r(rhs[col],p);if(!rv)return std::nullopt;rhs[col]=*rv;for(std::size_t row=0;row<n;++row){if(row==col)continue;R factor=matrix[row][col];for(std::size_t j=0;j<n;++j){auto product=mul_r(factor,matrix[col][j]),value=product?sub_r(matrix[row][j],*product):std::nullopt;if(!value)return std::nullopt;matrix[row][j]=*value;}auto product=mul_r(factor,rhs[col]),value=product?sub_r(rhs[row],*product):std::nullopt;if(!value)return std::nullopt;rhs[row]=*value;}}return rhs;''',
        r'''std::size_t n=matrix.size();if(n==0||rhs.size()!=n)return std::nullopt;std::vector<R> out;for(std::size_t i=0;i<n;++i){if(matrix[i].size()!=n)return std::nullopt;auto value=div_r(rhs[i],matrix[i][i]);if(!value)return std::nullopt;out.push_back(*value);}return out;''',
        "auto r=RationalLinearSystem{}.solve({{{2,1},{1,1}},{{1,1},{-1,1}}},{{5,1},{1,1}});return !r||r->size()!=2||!same((*r)[0],{2,1})||!same((*r)[1],{1,1});",
        "auto x=RationalLinearSystem{};auto r=x.solve({{{0,1},{1,1}},{{2,1},{3,1}}},{{1,1},{5,1}});return !r||!same((*r)[0],{1,1})||!same((*r)[1],{1,1})||x.solve({{{1,1},{2,1}},{{2,1},{4,1}}},{{1,1},{2,1}});",
        "Solve a square rational system by pivoting, row normalization, and elimination of every other row.",
        "Reject empty, ragged, dimension-mismatched, singular, invalid, or overflowing systems.",
        "Select the first nonzero pivot row at or below each column and return variables in column order.",
        "diagonal-only-solve"))
    add(ArithmeticCase(
        "rational-determinant-elimination", "Rational determinant", "rational",
        "row-pivoted exact elimination with swap parity",
        "std::optional<Rational> determinant(std::vector<std::vector<Rational>> matrix) const",
        "std::optional<Rational> {cls}::determinant(std::vector<std::vector<Rational>> matrix) const",
        r'''std::size_t n=matrix.size();if(n==0)return R{1,1};for(auto& row:matrix){if(row.size()!=n)return std::nullopt;for(auto& value:row){auto valid=normalized(value);if(!valid)return std::nullopt;value=*valid;}}R det{1,1};int sign=1;for(std::size_t col=0;col<n;++col){std::size_t pivot=col;while(pivot<n){auto v=normalized(matrix[pivot][col]);if(!v)return std::nullopt;if(v->numerator!=0){break;}++pivot;}if(pivot==n)return R{0,1};if(pivot!=col){std::swap(matrix[pivot],matrix[col]);sign=-sign;}R p=matrix[col][col];auto next_det=mul_r(det,p);if(!next_det)return std::nullopt;det=*next_det;for(std::size_t row=col+1;row<n;++row){auto factor=div_r(matrix[row][col],p);if(!factor)return std::nullopt;for(std::size_t j=col;j<n;++j){auto product=mul_r(*factor,matrix[col][j]),value=product?sub_r(matrix[row][j],*product):std::nullopt;if(!value)return std::nullopt;matrix[row][j]=*value;}}}if(sign<0)det.numerator=-det.numerator;return normalized(det);''',
        r'''if(matrix.empty())return R{1,1};R result{1,1};for(std::size_t i=0;i<matrix.size();++i){if(matrix[i].size()!=matrix.size())return std::nullopt;auto next=mul_r(result,matrix[i][i]);if(!next)return std::nullopt;result=*next;}return result;''',
        "auto r=RationalDeterminantElimination{}.determinant({{{1,1},{2,1}},{{3,1},{4,1}}});return !r||!same(*r,{-2,1});",
        "auto x=RationalDeterminantElimination{};auto swapped=x.determinant({{{0,1},{1,1}},{{2,1},{3,1}}});auto zero=x.determinant({{{1,1},{2,1}},{{2,1},{4,1}}});auto empty=x.determinant({});return !swapped||!same(*swapped,{-2,1})||!zero||!same(*zero,{0,1})||!empty||!same(*empty,{1,1})||x.determinant({{{0,1},{0,1}},{{0,1},{1,0}}});",
        "Compute a square rational determinant through exact pivoted elimination.",
        "Reject ragged, nonsquare, invalid, or overflowing matrices; an empty determinant is one.",
        "The first available nonzero pivot is used and each row swap flips the determinant sign.",
        "diagonal-product"))
    add(ArithmeticCase(
        "rational-distribution-convolution", "Rational distribution convolution", "rational",
        "exact linear probability-mass convolution",
        "std::optional<std::vector<Rational>> convolve(const std::vector<Rational>& left, const std::vector<Rational>& right) const",
        "std::optional<std::vector<Rational>> {cls}::convolve(const std::vector<Rational>& left, const std::vector<Rational>& right) const",
        r'''if(left.empty()||right.empty())return std::nullopt;auto valid=[](const std::vector<R>& v)->bool{R sum{0,1};for(R x:v){auto n=normalized(x);auto c=n?cmp_r(*n,{0,1}):std::nullopt;if(!n||!c||*c<0)return false;auto next=add_r(sum,*n);if(!next)return false;sum=*next;}return equal_r(sum,{1,1});};if(!valid(left)||!valid(right))return std::nullopt;std::vector<R> out(left.size()+right.size()-1,R{0,1});for(std::size_t i=0;i<left.size();++i)for(std::size_t j=0;j<right.size();++j){auto product=mul_r(left[i],right[j]),sum=product?add_r(out[i+j],*product):std::nullopt;if(!sum)return std::nullopt;out[i+j]=*sum;}return out;''',
        r'''if(left.empty()||right.empty())return std::nullopt;std::size_t n=std::min(left.size(),right.size());std::vector<R> out(n);for(std::size_t i=0;i<n;++i){auto v=mul_r(left[i],right[i]);if(!v)return std::nullopt;out[i]=*v;}return out;''',
        "auto r=RationalDistributionConvolution{}.convolve({{1,2},{1,2}},{{1,2},{1,2}});return !r||r->size()!=3||!same((*r)[0],{1,4})||!same((*r)[1],{1,2})||!same((*r)[2],{1,4});",
        "auto x=RationalDistributionConvolution{};auto r=x.convolve({{1,1}},{{1,3},{2,3}});return !r||r->size()!=2||!same((*r)[1],{2,3})||x.convolve({{1,2}},{{1,1}})||x.convolve({},{{1,1}});",
        "Convolve two normalized nonnegative exact mass functions without circular wraparound.",
        "Reject empty, negative, non-normalized, invalid, or overflowing distributions.",
        "Output indices increase by summed outcome index and length is m+n-1.",
        "pointwise-product"))
    add(ArithmeticCase(
        "rational-markov-transition", "Rational Markov transition", "rational",
        "exact row-vector stochastic-matrix multiplication",
        "std::optional<std::vector<Rational>> advance(const std::vector<Rational>& state, const std::vector<std::vector<Rational>>& transition) const",
        "std::optional<std::vector<Rational>> {cls}::advance(const std::vector<Rational>& state, const std::vector<std::vector<Rational>>& transition) const",
        r'''std::size_t n=state.size();if(n==0||transition.size()!=n)return std::nullopt;auto stochastic=[](const std::vector<R>& row)->bool{R sum{0,1};for(R x:row){auto c=cmp_r(x,{0,1});if(!c||*c<0)return false;auto next=add_r(sum,x);if(!next)return false;sum=*next;}return equal_r(sum,{1,1});};if(!stochastic(state))return std::nullopt;for(const auto& row:transition)if(row.size()!=n||!stochastic(row))return std::nullopt;std::vector<R> out(n,R{0,1});for(std::size_t i=0;i<n;++i)for(std::size_t j=0;j<n;++j){auto product=mul_r(state[i],transition[i][j]),sum=product?add_r(out[j],*product):std::nullopt;if(!sum)return std::nullopt;out[j]=*sum;}return out;''',
        r'''if(state.empty()||transition.size()!=state.size())return std::nullopt;std::vector<R> out;for(std::size_t i=0;i<state.size();++i){if(transition[i].size()!=state.size())return std::nullopt;std::size_t best=0;for(std::size_t j=1;j<state.size();++j){auto c=cmp_r(transition[i][j],transition[i][best]);if(c&&*c>0)best=j;}if(out.empty())out.assign(state.size(),R{0,1});auto sum=add_r(out[best],state[i]);if(!sum)return std::nullopt;out[best]=*sum;}return out;''',
        "auto r=RationalMarkovTransition{}.advance({{1,2},{1,2}},{{{1,2},{1,2}},{{1,4},{3,4}}});return !r||!same((*r)[0],{3,8})||!same((*r)[1],{5,8});",
        "auto x=RationalMarkovTransition{};auto r=x.advance({{1,1}},{{{1,1}}});return !r||!same((*r)[0],{1,1})||x.advance({{1,2}},{{{1,1}}})||x.advance({{1,1}},{{{2,1}}});",
        "Advance an exact state distribution through a row-stochastic transition matrix.",
        "Reject empty, dimension-mismatched, negative, non-stochastic, invalid, or overflowing inputs.",
        "Destination order is matrix column order; every source contributes to every destination.",
        "largest-edge-only"))
    return tuple(rows)


def _rational_cases_more() -> tuple[ArithmeticCase, ...]:
    rows: list[ArithmeticCase] = []
    add = rows.append
    add(ArithmeticCase(
        "rational-interval-union-measure", "Rational interval union", "rational",
        "sorted closed-interval merge followed by exact union measurement",
        "std::optional<Rational> measure(std::vector<RationalInterval> intervals) const",
        "std::optional<Rational> {cls}::measure(std::vector<RationalInterval> intervals) const",
        r'''for(const auto& interval:intervals){auto c=cmp_r(interval.begin,interval.end);if(!c||*c>0)return std::nullopt;}std::sort(intervals.begin(),intervals.end(),[](const auto&a,const auto&b){auto c=cmp_r(a.begin,b.begin);return c&&(*c<0||(*c==0&&cmp_r(a.end,b.end)&&*cmp_r(a.end,b.end)<0));});R total{0,1};if(intervals.empty())return total;R begin=*normalized(intervals[0].begin),end=*normalized(intervals[0].end);for(std::size_t i=1;i<intervals.size();++i){auto touch=cmp_r(intervals[i].begin,end);if(!touch)return std::nullopt;if(*touch<=0){auto farther=cmp_r(intervals[i].end,end);if(!farther)return std::nullopt;if(*farther>0)end=*normalized(intervals[i].end);}else{auto length=sub_r(end,begin),sum=length?add_r(total,*length):std::nullopt;if(!sum)return std::nullopt;total=*sum;begin=*normalized(intervals[i].begin);end=*normalized(intervals[i].end);}}auto length=sub_r(end,begin),sum=length?add_r(total,*length):std::nullopt;return sum;''',
        r'''R total{0,1};for(const auto& interval:intervals){auto length=sub_r(interval.end,interval.begin),sum=length?add_r(total,*length):std::nullopt;if(!sum)return std::nullopt;total=*sum;}return total;''',
        "auto r=RationalIntervalUnionMeasure{}.measure({{{0,1},{3,2}},{{1,1},{2,1}},{{3,1},{7,2}}});return !r||!same(*r,{5,2});",
        "auto x=RationalIntervalUnionMeasure{};auto empty=x.measure({});auto touch=x.measure({{{0,1},{1,1}},{{1,1},{3,1}}});return !empty||!same(*empty,{0,1})||!touch||!same(*touch,{3,1})||x.measure({{{2,1},{1,1}}});",
        "Sort and merge overlapping or touching exact intervals before summing their union length.",
        "Reject invalid rationals and any interval whose begin exceeds its end; empty input measures zero.",
        "Sort by begin then end and merge into increasing disjoint spans.",
        "unmerged-length-sum", "struct RationalInterval { Rational begin; Rational end; };"))
    add(ArithmeticCase(
        "rational-piecewise-rate-integral", "Piecewise rational rate integral", "rational",
        "query-window clipping and exact rate-times-duration accumulation",
        "std::optional<Rational> integrate(std::vector<RateSegment> segments, Rational begin, Rational end) const",
        "std::optional<Rational> {cls}::integrate(std::vector<RateSegment> segments, Rational begin, Rational end) const",
        r'''auto query=cmp_r(begin,end);if(!query||*query>0)return std::nullopt;std::sort(segments.begin(),segments.end(),[](const auto&a,const auto&b){auto c=cmp_r(a.begin,b.begin);return c&&*c<0;});R total{0,1};std::optional<R> previous;for(const auto& segment:segments){auto order=cmp_r(segment.begin,segment.end),nonnegative=cmp_r(segment.rate,{0,1});if(!order||!nonnegative||*order>0||*nonnegative<0)return std::nullopt;if(previous){auto overlap=cmp_r(segment.begin,*previous);if(!overlap||*overlap<0)return std::nullopt;}previous=normalized(segment.end);auto lo_cmp=cmp_r(segment.begin,begin),hi_cmp=cmp_r(segment.end,end);if(!lo_cmp||!hi_cmp)return std::nullopt;R lo=*lo_cmp<0?begin:segment.begin,hi=*hi_cmp>0?end:segment.end;auto width_cmp=cmp_r(lo,hi);if(!width_cmp)return std::nullopt;if(*width_cmp<0){auto width=sub_r(hi,lo),area=width?mul_r(*width,segment.rate):std::nullopt,sum=area?add_r(total,*area):std::nullopt;if(!sum)return std::nullopt;total=*sum;}}return total;''',
        r'''static_cast<void>(begin);static_cast<void>(end);R total{0,1};for(const auto& segment:segments){auto width=sub_r(segment.end,segment.begin),area=width?mul_r(*width,segment.rate):std::nullopt,sum=area?add_r(total,*area):std::nullopt;if(!sum)return std::nullopt;total=*sum;}return total;''',
        "auto r=RationalPiecewiseRateIntegral{}.integrate({{{0,1},{2,1},{3,1}},{{2,1},{5,1},{1,2}}},{1,1},{3,1});return !r||!same(*r,{7,2});",
        "auto x=RationalPiecewiseRateIntegral{};auto zero=x.integrate({}, {2,1},{2,1});return !zero||!same(*zero,{0,1})||x.integrate({{{0,1},{2,1},{1,1}},{{1,1},{3,1},{1,1}}},{0,1},{3,1})||x.integrate({}, {2,1},{1,1});",
        "Clip each nonoverlapping half-open rate segment to a rational query window and integrate exactly.",
        "Reject reversed queries, overlapping/reversed segments, negative rates, invalid values, or overflow.",
        "Sort by segment begin; touching segments are allowed and each clipped contribution is accumulated once.",
        "unclipped-segment-total", "struct RateSegment { Rational begin; Rational end; Rational rate; };"))
    add(ArithmeticCase(
        "rational-segment-intersection", "Exact segment intersection", "rational",
        "exact cross-product line parameters and closed-segment membership",
        "std::optional<RationalPoint> intersect(RationalPoint a, RationalPoint b, RationalPoint c, RationalPoint d) const",
        "std::optional<RationalPoint> {cls}::intersect(RationalPoint a, RationalPoint b, RationalPoint c, RationalPoint d) const",
        r'''auto subp=[](RationalPoint p,RationalPoint q)->std::optional<RationalPoint>{auto x=sub_r(p.x,q.x),y=sub_r(p.y,q.y);if(!x||!y)return std::nullopt;return RationalPoint{*x,*y};};auto cross=[](RationalPoint p,RationalPoint q)->std::optional<R>{auto a=mul_r(p.x,q.y),b=mul_r(p.y,q.x);return a&&b?sub_r(*a,*b):std::nullopt;};auto r=subp(b,a),s=subp(d,c),ca=subp(c,a);if(!r||!s||!ca)return std::nullopt;auto den=cross(*r,*s),tn=cross(*ca,*s),un=cross(*ca,*r);if(!den||!tn||!un||den->numerator==0)return std::nullopt;auto t=div_r(*tn,*den),u=div_r(*un,*den);if(!t||!u)return std::nullopt;auto t0=cmp_r(*t,{0,1}),t1=cmp_r(*t,{1,1}),u0=cmp_r(*u,{0,1}),u1=cmp_r(*u,{1,1});if(!t0||!t1||!u0||!u1||*t0<0||*t1>0||*u0<0||*u1>0)return std::nullopt;auto dx=mul_r(r->x,*t),dy=mul_r(r->y,*t),x=dx?add_r(a.x,*dx):std::nullopt,y=dy?add_r(a.y,*dy):std::nullopt;if(!x||!y)return std::nullopt;return RationalPoint{*x,*y};''',
        r'''auto x1=add_r(a.x,b.x),y1=add_r(a.y,b.y),x2=add_r(c.x,d.x),y2=add_r(c.y,d.y);if(!x1||!y1||!x2||!y2)return std::nullopt;auto p=div_r(*x1,{2,1}),q=div_r(*y1,{2,1});if(!p||!q)return std::nullopt;return RationalPoint{*p,*q};''',
        "auto r=RationalSegmentIntersection{}.intersect({{0,1},{0,1}},{{2,1},{2,1}},{{0,1},{2,1}},{{2,1},{0,1}});return !r||!same(r->x,{1,1})||!same(r->y,{1,1});",
        "auto x=RationalSegmentIntersection{};auto endpoint=x.intersect({{0,1},{0,1}},{{1,1},{0,1}},{{1,1},{0,1}},{{1,1},{2,1}});return !endpoint||!same(endpoint->x,{1,1})||x.intersect({{0,1},{0,1}},{{1,1},{0,1}},{{0,1},{1,1}},{{1,1},{1,1}});",
        "Compute a unique closed-segment intersection through exact vector cross products.",
        "Reject invalid, degenerate, parallel, collinear, disjoint, or overflowing segments.",
        "Endpoint contact is included; the returned point is independent of endpoint direction.",
        "bounding-box-midpoint", "struct RationalPoint { Rational x; Rational y; };"))
    add(ArithmeticCase(
        "rational-polygon-centroid", "Exact polygon centroid", "rational",
        "shoelace signed-area and first-moment accumulation",
        "std::optional<RationalPoint> centroid(std::vector<RationalPoint> polygon) const",
        "std::optional<RationalPoint> {cls}::centroid(std::vector<RationalPoint> polygon) const",
        r'''if(polygon.size()>1&&equal_r(polygon.front().x,polygon.back().x)&&equal_r(polygon.front().y,polygon.back().y))polygon.pop_back();if(polygon.size()<3)return std::nullopt;R twice{0,1},sx{0,1},sy{0,1};for(std::size_t i=0;i<polygon.size();++i){const auto&a=polygon[i];const auto&b=polygon[(i+1)%polygon.size()];auto p=mul_r(a.x,b.y),q=mul_r(b.x,a.y),cross=p&&q?sub_r(*p,*q):std::nullopt;if(!cross)return std::nullopt;auto area=add_r(twice,*cross),xs=add_r(a.x,b.x),ys=add_r(a.y,b.y);auto xt=xs?mul_r(*xs,*cross):std::nullopt,yt=ys?mul_r(*ys,*cross):std::nullopt;auto nx=xt?add_r(sx,*xt):std::nullopt,ny=yt?add_r(sy,*yt):std::nullopt;if(!area||!nx||!ny)return std::nullopt;twice=*area;sx=*nx;sy=*ny;}if(twice.numerator==0)return std::nullopt;auto denominator=mul_r({3,1},twice),x=denominator?div_r(sx,*denominator):std::nullopt,y=denominator?div_r(sy,*denominator):std::nullopt;if(!x||!y)return std::nullopt;return RationalPoint{*x,*y};''',
        r'''if(polygon.empty())return std::nullopt;R x{0,1},y{0,1};for(const auto&p:polygon){auto nx=add_r(x,p.x),ny=add_r(y,p.y);if(!nx||!ny)return std::nullopt;x=*nx;y=*ny;}auto cx=div_r(x,{static_cast<long long>(polygon.size()),1}),cy=div_r(y,{static_cast<long long>(polygon.size()),1});if(!cx||!cy)return std::nullopt;return RationalPoint{*cx,*cy};''',
        "auto r=RationalPolygonCentroid{}.centroid({{{0,1},{0,1}},{{4,1},{0,1}},{{0,1},{2,1}}});return !r||!same(r->x,{4,3})||!same(r->y,{2,3});",
        "auto x=RationalPolygonCentroid{};auto r=x.centroid({{{0,1},{0,1}},{{0,1},{2,1}},{{4,1},{0,1}},{{0,1},{0,1}}});return !r||!same(r->x,{4,3})||!same(r->y,{2,3})||x.centroid({{{0,1},{0,1}},{{1,1},{1,1}},{{2,1},{2,1}}});",
        "Compute an orientation-independent exact polygon centroid from signed shoelace moments.",
        "Reject fewer than three effective vertices, zero area, invalid rationals, or overflow.",
        "Preserve cyclic edge order; one repeated closing vertex is removed before processing.",
        "vertex-arithmetic-mean", "struct RationalPoint { Rational x; Rational y; };"))
    add(ArithmeticCase(
        "rational-bezier-split", "Rational Bezier split", "rational",
        "de Casteljau triangle producing both ordered control polygons",
        "std::optional<BezierSplit> split(std::vector<RationalPoint> controls, Rational t) const",
        "std::optional<BezierSplit> {cls}::split(std::vector<RationalPoint> controls, Rational t) const",
        r'''auto parameter=normalized(t);auto low=parameter?cmp_r(*parameter,{0,1}):std::nullopt;auto high=parameter?cmp_r(*parameter,{1,1}):std::nullopt;if(controls.empty()||!parameter||!low||!high||*low<0||*high>0)return std::nullopt;for(auto& point:controls){auto x=normalized(point.x),y=normalized(point.y);if(!x||!y)return std::nullopt;point={*x,*y};}auto one_minus=sub_r({1,1},*parameter);if(!one_minus)return std::nullopt;BezierSplit out;out.left.push_back(controls.front());out.right.push_back(controls.back());while(controls.size()>1){std::vector<RationalPoint> next;for(std::size_t i=0;i+1<controls.size();++i){auto ax=mul_r(controls[i].x,*one_minus),bx=mul_r(controls[i+1].x,*parameter),ay=mul_r(controls[i].y,*one_minus),by=mul_r(controls[i+1].y,*parameter);auto x=ax&&bx?add_r(*ax,*bx):std::nullopt,y=ay&&by?add_r(*ay,*by):std::nullopt;if(!x||!y)return std::nullopt;next.push_back({*x,*y});}out.left.push_back(next.front());out.right.push_back(next.back());controls=std::move(next);}std::reverse(out.right.begin(),out.right.end());return out;''',
        r'''auto p=normalized(t);if(controls.empty()||!p)return std::nullopt;BezierSplit out;out.left={controls.front()};out.right={controls.back()};return out;''',
        "auto r=RationalBezierSplit{}.split({{{0,1},{0,1}},{{2,1},{2,1}},{{4,1},{0,1}}},{1,2});return !r||r->left.size()!=3||r->right.size()!=3||!same(r->left.back().x,{2,1})||!same(r->left[1].y,{1,1});",
        "auto x=RationalBezierSplit{};auto r=x.split({{{1,1},{2,1}},{{3,1},{4,1}}},{0,1});return !r||!same(r->left.back().x,{1,1})||!same(r->right.back().x,{3,1})||x.split({}, {1,2})||x.split({{{0,1},{0,1}}},{2,1})||x.split({{{1,0},{2,1}}},{1,2});",
        "Build the complete de Casteljau triangle and return its left and right control boundaries.",
        "Reject empty controls, t outside [0,1], invalid rationals, or overflow.",
        "Left runs from the original first point to the split point; right runs from split to original last.",
        "endpoint-only-interpolation", "struct RationalPoint { Rational x; Rational y; }; struct BezierSplit { std::vector<RationalPoint> left; std::vector<RationalPoint> right; };"))
    add(ArithmeticCase(
        "rational-conversion-path", "Exact conversion path", "rational",
        "lexically stable breadth-first multiplicative ratio propagation",
        "std::optional<Rational> convert(const std::vector<RatioEdge>& edges, const std::string& from, const std::string& to, Rational amount) const",
        "std::optional<Rational> {cls}::convert(const std::vector<RatioEdge>& edges, const std::string& from, const std::string& to, Rational amount) const",
        r'''auto start=normalized(amount);if(!start||from.empty()||to.empty())return std::nullopt;if(from==to)return start;std::map<std::string,std::vector<std::pair<std::string,R>>> graph;for(const auto&e:edges){auto ratio=normalized(e.multiplier);auto positive=ratio?cmp_r(*ratio,{0,1}):std::nullopt;if(e.from.empty()||e.to.empty()||!ratio||!positive||*positive<=0)return std::nullopt;graph[e.from].push_back({e.to,*ratio});auto inverse=div_r({1,1},*ratio);if(!inverse)return std::nullopt;graph[e.to].push_back({e.from,*inverse});}for(auto&entry:graph)std::sort(entry.second.begin(),entry.second.end(),[](const auto&a,const auto&b){return a.first<b.first;});std::queue<std::string> pending;std::map<std::string,R> values;pending.push(from);values[from]=*start;while(!pending.empty()){std::string current=pending.front();pending.pop();for(const auto&edge:graph[current]){auto next=mul_r(values[current],edge.second);if(!next)return std::nullopt;auto found=values.find(edge.first);if(found!=values.end()){if(!equal_r(found->second,*next))return std::nullopt;continue;}values[edge.first]=*next;pending.push(edge.first);}}auto result=values.find(to);if(result==values.end())return std::nullopt;return result->second;''',
        r'''auto start=normalized(amount);if(!start||from.empty()||to.empty())return std::nullopt;if(from==to)return start;for(const auto&e:edges)if(e.from==from&&e.to==to)return mul_r(*start,e.multiplier);return std::nullopt;''',
        "auto r=RationalConversionPath{}.convert({{\"m\",\"cm\",{100,1}},{\"cm\",\"mm\",{10,1}}},\"m\",\"mm\",{3,2});return !r||!same(*r,{1500,1});",
        "auto x=RationalConversionPath{};auto same_unit=x.convert({},\"x\",\"x\",{5,7});return !same_unit||!same(*same_unit,{5,7})||x.convert({{\"a\",\"b\",{2,1}},{\"a\",\"b\",{3,1}}},\"a\",\"b\",{1,1})||x.convert({},\"a\",\"b\",{1,1});",
        "Propagate exact bidirectional conversion ratios along a shortest path.",
        "Reject empty names, nonpositive ratios, inconsistent rediscovery, missing paths, invalid values, or overflow.",
        "Breadth-first search chooses fewest edges and visits equal-depth neighbors lexically.",
        "direct-edge-only", "struct RatioEdge { std::string from; std::string to; Rational multiplier; };"))
    add(ArithmeticCase(
        "rational-amortization-schedule", "Exact amortization schedule", "rational",
        "sequential exact interest accrual, payment subtraction, and zero-floor payoff propagation",
        "std::optional<std::vector<Rational>> balances(Rational principal, Rational periodic_rate, Rational payment, std::size_t periods) const",
        "std::optional<std::vector<Rational>> {cls}::balances(Rational principal, Rational periodic_rate, Rational payment, std::size_t periods) const",
        r'''auto balance=normalized(principal),rate=normalized(periodic_rate),paid=normalized(payment);auto principal_cmp=balance?cmp_r(*balance,{0,1}):std::nullopt;auto rate_cmp=rate?cmp_r(*rate,{0,1}):std::nullopt;auto payment_cmp=paid?cmp_r(*paid,{0,1}):std::nullopt;if(!balance||!rate||!paid||!principal_cmp||!rate_cmp||!payment_cmp||*principal_cmp<=0||*rate_cmp<0||*payment_cmp<=0||periods==0)return std::nullopt;std::vector<R> out;out.reserve(periods);for(std::size_t period=0;period<periods;++period){if(balance->numerator==0){out.push_back(*balance);continue;}auto interest=mul_r(*balance,*rate);auto accrued=interest?add_r(*balance,*interest):std::nullopt;auto next=accrued?sub_r(*accrued,*paid):std::nullopt;if(!next)return std::nullopt;auto order=cmp_r(*next,{0,1});if(!order)return std::nullopt;balance=*order<=0?R{0,1}:*next;out.push_back(*balance);}return out;''',
        r'''auto balance=normalized(principal),rate=normalized(periodic_rate),paid=normalized(payment);if(!balance||!rate||!paid||periods==0)return std::nullopt;auto fixed_interest=mul_r(*balance,*rate);if(!fixed_interest)return std::nullopt;std::vector<R> out;for(std::size_t period=0;period<periods;++period){auto accrued=add_r(*balance,*fixed_interest);auto next=accrued?sub_r(*accrued,*paid):std::nullopt;if(!next)return std::nullopt;balance=next;out.push_back(*balance);}return out;''',
        "auto r=RationalAmortizationSchedule{}.balances({100,1},{1,10},{30,1},3);return !r||r->size()!=3||!same((*r)[0],{80,1})||!same((*r)[1],{58,1})||!same((*r)[2],{169,5});",
        "auto x=RationalAmortizationSchedule{};auto r=x.balances({10,1},{0,1},{6,1},3);return !r||r->size()!=3||!same((*r)[0],{4,1})||!same((*r)[1],{0,1})||!same((*r)[2],{0,1})||x.balances({10,0},{0,1},{1,1},2)||x.balances({10,1},{-1,10},{1,1},2)||x.balances({10,1},{0,1},{0,1},2)||x.balances({10,1},{0,1},{1,1},0);",
        "Accrue exact periodic interest on the current balance, subtract one payment, and emit every post-payment balance.",
        "Reject invalid or nonpositive principal/payment, negative rate, zero periods, or any overflowing intermediate.",
        "Balances are sequential: after payoff, emit canonical zero for every remaining period without accruing again.",
        "simple-interest-from-original-principal"))
    add(ArithmeticCase(
        "rational-largest-remainder", "Largest-remainder allocation", "rational",
        "exact quota floors followed by stable descending remainder assignment",
        "std::optional<std::vector<long long>> allocate(const std::vector<Rational>& weights, long long seats) const",
        "std::optional<std::vector<long long>> {cls}::allocate(const std::vector<Rational>& weights, long long seats) const",
        r'''if(weights.empty()||seats<0)return std::nullopt;R total{0,1};for(R w:weights){auto nonnegative=cmp_r(w,{0,1});auto next=nonnegative?add_r(total,w):std::nullopt;if(!nonnegative||*nonnegative<0||!next)return std::nullopt;total=*next;}if(total.numerator==0)return std::nullopt;std::vector<long long> out(weights.size());std::vector<std::pair<R,std::size_t>> remainder;long long used=0;for(std::size_t i=0;i<weights.size();++i){auto scaled=mul_r(weights[i],{seats,1}),quota=scaled?div_r(*scaled,total):std::nullopt;if(!quota)return std::nullopt;long long floor=quota->numerator/quota->denominator;if(!add_ll(used,floor,used))return std::nullopt;out[i]=floor;auto rest=sub_r(*quota,{floor,1});if(!rest)return std::nullopt;remainder.push_back({*rest,i});}std::stable_sort(remainder.begin(),remainder.end(),[](const auto&a,const auto&b){auto c=cmp_r(a.first,b.first);return c&&(*c>0||(*c==0&&a.second<b.second));});for(long long k=used;k<seats;++k)++out[remainder[static_cast<std::size_t>(k-used)].second];return out;''',
        r'''if(weights.empty()||seats<0)return std::nullopt;R total{0,1};for(R w:weights){auto next=add_r(total,w);if(!next)return std::nullopt;total=*next;}std::vector<long long> out;for(R w:weights){auto quota=div_r(*mul_r(w,{seats,1}),total);if(!quota)return std::nullopt;out.push_back((quota->numerator+quota->denominator/2)/quota->denominator);}return out;''',
        "auto r=RationalLargestRemainder{}.allocate({{1,1},{1,1},{1,1}},5);return !r||*r!=std::vector<long long>({2,2,1});",
        "auto x=RationalLargestRemainder{};auto zero=x.allocate({{1,1},{3,1}},0);return !zero||*zero!=std::vector<long long>({0,0})||x.allocate({{0,1},{0,1}},3)||x.allocate({{-1,1},{2,1}},3);",
        "Allocate integer seats from exact quotas using floors and largest fractional remainders.",
        "Reject empty weights, negative weights or seats, zero total weight, invalid values, or overflow.",
        "Remainder ties choose the smaller original index and the result preserves input order.",
        "independent-quota-rounding"))
    add(ArithmeticCase(
        "rational-repeating-decimal", "Repeating decimal decoder", "rational",
        "whole-input decimal grammar and exact finite/repeating place-value conversion",
        "std::optional<Rational> decode(const std::string& text) const",
        "std::optional<Rational> {cls}::decode(const std::string& text) const",
        r'''if(text.empty())return std::nullopt;std::size_t pos=0;int sign=1;if(text[pos]=='+'||text[pos]=='-'){if(text[pos++]=='-')sign=-1;if(pos==text.size())return std::nullopt;}long long whole=0;std::size_t integer_digits=0;while(pos<text.size()&&std::isdigit(static_cast<unsigned char>(text[pos]))){long long next;if(!mul_ll(whole,10,next)||!add_ll(next,text[pos]-'0',whole))return std::nullopt;++pos;++integer_digits;}if(integer_digits==0)return std::nullopt;std::string finite,repeat;if(pos<text.size()&&text[pos]=='.'){++pos;while(pos<text.size()&&std::isdigit(static_cast<unsigned char>(text[pos])))finite.push_back(text[pos++]);if(pos<text.size()&&text[pos]=='('){++pos;while(pos<text.size()&&std::isdigit(static_cast<unsigned char>(text[pos])))repeat.push_back(text[pos++]);if(repeat.empty()||pos>=text.size()||text[pos]!=')')return std::nullopt;++pos;}}if(pos!=text.size())return std::nullopt;long long power=1,finite_value=0;for(char ch:finite){if(!mul_ll(power,10,power)||!mul_ll(finite_value,10,finite_value)||!add_ll(finite_value,ch-'0',finite_value))return std::nullopt;}auto result=add_r({whole,1},{finite_value,power});if(!result)return std::nullopt;if(!repeat.empty()){long long repeated=0,repeat_power=1;for(char ch:repeat){if(!mul_ll(repeat_power,10,repeat_power)||!mul_ll(repeated,10,repeated)||!add_ll(repeated,ch-'0',repeated))return std::nullopt;}long long cycle;if(!sub_ll(repeat_power,1,cycle))return std::nullopt;auto part=div_r({repeated,1},{power,1});part=part?div_r(*part,{cycle,1}):std::nullopt;result=part?add_r(*result,*part):std::nullopt;if(!result)return std::nullopt;}if(sign<0){if(result->numerator==std::numeric_limits<long long>::min())return std::nullopt;result->numerator=-result->numerator;}return normalized(*result);''',
        r'''try{std::size_t used=0;long double value=std::stold(text,&used);if(used!=text.size())return std::nullopt;return normalized({static_cast<long long>(value*1000000.0L),1000000});}catch(...){return std::nullopt;}''',
        "auto r=RationalRepeatingDecimal{}.decode(\"0.1(6)\");return !r||!same(*r,{1,6});",
        "auto x=RationalRepeatingDecimal{};auto r=x.decode(\"-12.34(0)\");return !r||!same(*r,{-617,50})||x.decode(\".5\")||x.decode(\"1.()\")||x.decode(\"1.2x\");",
        "Parse and exactly convert a signed decimal with optional finite and parenthesized repeating fractional parts.",
        "Reject incomplete signs, missing integer digits, empty/unclosed repeats, trailing input, or overflow.",
        "Consume the complete ASCII input; a repeating zero block is accepted and canonicalized away.",
        "finite-decimal-only"))
    return tuple(rows)


RATIONAL_CASES = _rational_cases() + _rational_cases_more()


GAUSSIAN_SUPPORT = r'''
namespace {
using G = Gaussian;
bool mul_ll(long long a,long long b,long long& out){return !__builtin_mul_overflow(a,b,&out);}
bool add_ll(long long a,long long b,long long& out){return !__builtin_add_overflow(a,b,&out);}
bool sub_ll(long long a,long long b,long long& out){return !__builtin_sub_overflow(a,b,&out);}
std::optional<long long> norm_g(G value){long long a,b,n;if(!mul_ll(value.real,value.real,a)||!mul_ll(value.imag,value.imag,b)||!add_ll(a,b,n))return std::nullopt;return n;}
std::optional<G> mul_g(G a,G b){long long ac,bd,ad,bc,r,i;if(!mul_ll(a.real,b.real,ac)||!mul_ll(a.imag,b.imag,bd)||!mul_ll(a.real,b.imag,ad)||!mul_ll(a.imag,b.real,bc)||!sub_ll(ac,bd,r)||!add_ll(ad,bc,i))return std::nullopt;return G{r,i};}
G canonical_g(G value){G choices[4]={{value.real,value.imag},{-value.real,-value.imag},{-value.imag,value.real},{value.imag,-value.real}};G best=choices[0];for(G item:choices)if(item.real>best.real||(item.real==best.real&&item.imag>best.imag))best=item;return best;}
}  // namespace
'''


COMPLEX_SUPPORT = r'''
namespace {
using C = ComplexValue;
bool finite_c(C z){return std::isfinite(z.real)&&std::isfinite(z.imag);}
C add_c(C a,C b){return {a.real+b.real,a.imag+b.imag};}
C sub_c(C a,C b){return {a.real-b.real,a.imag-b.imag};}
C mul_c(C a,C b){return {a.real*b.real-a.imag*b.imag,a.real*b.imag+a.imag*b.real};}
C scale_c(C a,long double s){return {a.real*s,a.imag*s};}
C conj_c(C a){return {a.real,-a.imag};}
long double norm_c(C a){return a.real*a.real+a.imag*a.imag;}
std::optional<C> div_c(C a,C b){long double d=norm_c(b);if(!finite_c(a)||!finite_c(b)||!std::isfinite(d)||d<=1e-24L)return std::nullopt;C out{(a.real*b.real+a.imag*b.imag)/d,(a.imag*b.real-a.real*b.imag)/d};return finite_c(out)?std::optional<C>(out):std::nullopt;}
bool all_finite(const std::vector<C>& values){return std::all_of(values.begin(),values.end(),finite_c);}
}  // namespace
'''


def _complex_cases_first() -> tuple[ArithmeticCase, ...]:
    rows: list[ArithmeticCase] = []
    add = rows.append
    add(ArithmeticCase(
        "gaussian-euclidean-gcd", "Gaussian Euclidean gcd", "gaussian",
        "nearest-quotient Euclidean descent in the Gaussian integer lattice",
        "std::optional<Gaussian> gcd(Gaussian a, Gaussian b) const",
        "std::optional<Gaussian> {cls}::gcd(Gaussian a, Gaussian b) const",
        r'''long long minimum=std::numeric_limits<long long>::min();if(a.real==minimum||a.imag==minimum||b.real==minimum||b.imag==minimum)return std::nullopt;if(a.real==0&&a.imag==0&&b.real==0&&b.imag==0)return std::nullopt;while(b.real!=0||b.imag!=0){auto denominator=norm_g(b);if(!denominator||*denominator==0)return std::nullopt;long long p1,p2,p3,p4,real_num,imag_num;if(!mul_ll(a.real,b.real,p1)||!mul_ll(a.imag,b.imag,p2)||!mul_ll(a.imag,b.real,p3)||!mul_ll(a.real,b.imag,p4)||!add_ll(p1,p2,real_num)||!sub_ll(p3,p4,imag_num))return std::nullopt;long long qr=std::llround(static_cast<long double>(real_num)/static_cast<long double>(*denominator));long long qi=std::llround(static_cast<long double>(imag_num)/static_cast<long double>(*denominator));auto product=mul_g({qr,qi},b);if(!product)return std::nullopt;long long rr,ri;if(!sub_ll(a.real,product->real,rr)||!sub_ll(a.imag,product->imag,ri))return std::nullopt;a=b;b={rr,ri};}return canonical_g(a);''',
        r'''long long ar=std::llabs(a.real),br=std::llabs(b.real);while(br){long long t=ar%br;ar=br;br=t;}long long ai=std::llabs(a.imag),bi=std::llabs(b.imag);while(bi){long long t=ai%bi;ai=bi;bi=t;}return canonical_g({ar,ai});''',
        "auto r=GaussianEuclideanGcd{}.gcd({3,1},{1,1});return !r||r->real!=1||r->imag!=1;",
        "auto x=GaussianEuclideanGcd{};auto r=x.gcd({5,0},{2,1});long long minimum=std::numeric_limits<long long>::min();return !r||r->real!=2||r->imag!=1||x.gcd({0,0},{0,0})||x.gcd({minimum,0},{0,0})||x.gcd({0,0},{0,minimum});",
        "Run Gaussian Euclidean division using the nearest lattice quotient until the remainder is zero.",
        "Reject two zero operands and any checked norm/product overflow.",
        "Canonicalize the final associate by greatest real component then greatest imaginary component.",
        "componentwise-integer-gcd", "struct Gaussian { long long real; long long imag; };"))
    add(ArithmeticCase(
        "gaussian-divisibility-lattice", "Gaussian divisor lattice", "gaussian",
        "norm-bounded lattice enumeration with exact Gaussian divisibility",
        "std::optional<std::vector<Gaussian>> divisors(Gaussian value, long long max_norm) const",
        "std::optional<std::vector<Gaussian>> {cls}::divisors(Gaussian value, long long max_norm) const",
        r'''if((value.real==0&&value.imag==0)||max_norm<1)return std::nullopt;long long bound=static_cast<long long>(std::sqrt(static_cast<long double>(max_norm)));std::vector<G> out;for(long long r=-bound;r<=bound;++r)for(long long i=-bound;i<=bound;++i){G divisor{r,i};auto n=norm_g(divisor);if(!n||*n==0||*n>max_norm)continue;long long p1,p2,p3,p4,real_num,imag_num;if(!mul_ll(value.real,r,p1)||!mul_ll(value.imag,i,p2)||!mul_ll(value.imag,r,p3)||!mul_ll(value.real,i,p4)||!add_ll(p1,p2,real_num)||!sub_ll(p3,p4,imag_num))return std::nullopt;if(real_num%*n==0&&imag_num%*n==0)out.push_back(divisor);}std::sort(out.begin(),out.end(),[](G a,G b){auto na=norm_g(a),nb=norm_g(b);return *na<*nb||(*na==*nb&&(a.real<b.real||(a.real==b.real&&a.imag<b.imag)));});return out;''',
        r'''if((value.real==0&&value.imag==0)||max_norm<1)return std::nullopt;std::vector<G> out;for(long long r=-max_norm;r<=max_norm;++r)for(long long i=-max_norm;i<=max_norm;++i)if((r||i)&&value.real%(r?r:1)==0&&value.imag%(i?i:1)==0)out.push_back({r,i});return out;''',
        "auto r=GaussianDivisibilityLattice{}.divisors({2,0},2);return !r||!contains(*r,{1,1})||!contains(*r,{-1,1});",
        "auto x=GaussianDivisibilityLattice{};auto r=x.divisors({1,1},1);return !r||r->size()!=4||x.divisors({0,0},4)||x.divisors({1,0},0);",
        "Enumerate every nonzero Gaussian divisor inside an inclusive squared-norm bound.",
        "Reject a zero dividend, a bound below one, or checked arithmetic overflow.",
        "Sort divisors by norm, then real component, then imaginary component; emit no duplicates.",
        "rectangular-component-divisibility", "struct Gaussian { long long real; long long imag; };"))
    add(ArithmeticCase(
        "complex-polynomial-horner", "Complex polynomial evaluation", "complex",
        "highest-degree-first complex Horner fold",
        "std::optional<ComplexValue> evaluate(const std::vector<ComplexValue>& coefficients, ComplexValue x) const",
        "std::optional<ComplexValue> {cls}::evaluate(const std::vector<ComplexValue>& coefficients, ComplexValue x) const",
        r'''if(coefficients.empty()||!all_finite(coefficients)||!finite_c(x))return std::nullopt;C acc{0,0};for(C coefficient:coefficients){acc=add_c(mul_c(acc,x),coefficient);if(!finite_c(acc))return std::nullopt;}return acc;''',
        r'''static_cast<void>(x);if(coefficients.empty()||!all_finite(coefficients))return std::nullopt;C acc{0,0};for(C coefficient:coefficients)acc=add_c(acc,coefficient);return acc;''',
        "auto r=ComplexPolynomialHorner{}.evaluate({{1,0},{0,1},{-1,0}},{1,1});return !r||!close(*r,{-2,3});",
        "auto x=ComplexPolynomialHorner{};auto r=x.evaluate({{0,0},{2,-1}},{5,7});return !r||!close(*r,{2,-1})||x.evaluate({}, {0,0});",
        "Evaluate a complex-coefficient polynomial through a complex Horner fold.",
        "Reject empty coefficients and any nonfinite input or intermediate.",
        "Consume coefficients from highest degree to constant and preserve zero leading coefficients.",
        "coefficient-sum", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-polynomial-derivative", "Complex polynomial derivative", "complex",
        "degree-weighted derivative construction and Horner evaluation",
        "std::optional<ComplexValue> derivative_at(const std::vector<ComplexValue>& coefficients, ComplexValue x) const",
        "std::optional<ComplexValue> {cls}::derivative_at(const std::vector<ComplexValue>& coefficients, ComplexValue x) const",
        r'''if(coefficients.empty()||!all_finite(coefficients)||!finite_c(x))return std::nullopt;if(coefficients.size()==1)return C{0,0};C acc{0,0};for(std::size_t i=0;i+1<coefficients.size();++i){long double degree=static_cast<long double>(coefficients.size()-1-i);acc=add_c(mul_c(acc,x),scale_c(coefficients[i],degree));if(!finite_c(acc))return std::nullopt;}return acc;''',
        r'''if(coefficients.empty()||!all_finite(coefficients)||!finite_c(x))return std::nullopt;C acc{0,0};for(C coefficient:coefficients)acc=add_c(mul_c(acc,x),coefficient);return acc;''',
        "auto r=ComplexPolynomialDerivative{}.derivative_at({{1,0},{0,0},{1,0}},{0,2});return !r||!close(*r,{0,4});",
        "auto x=ComplexPolynomialDerivative{};auto r=x.derivative_at({{3,-2}},{7,9});return !r||!close(*r,{0,0})||x.derivative_at({}, {0,0});",
        "Weight coefficients by degree and evaluate the resulting derivative exactly in complex arithmetic.",
        "Reject empty or nonfinite input; a constant polynomial has zero derivative.",
        "Degree weights descend with coefficient order and the constant term is omitted.",
        "original-polynomial-evaluation", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-newton-iteration", "Complex Newton iteration", "complex",
        "guarded repeated polynomial/derivative evaluation and complex Newton division",
        "std::optional<ComplexValue> iterate(const std::vector<ComplexValue>& coefficients, ComplexValue start, std::size_t steps) const",
        "std::optional<ComplexValue> {cls}::iterate(const std::vector<ComplexValue>& coefficients, ComplexValue start, std::size_t steps) const",
        r'''if(coefficients.size()<2||steps>1000||!all_finite(coefficients)||!finite_c(start))return std::nullopt;C z=start;for(std::size_t step=0;step<steps;++step){C value{0,0},derivative{0,0};for(std::size_t i=0;i<coefficients.size();++i){value=add_c(mul_c(value,z),coefficients[i]);if(i+1<coefficients.size()){long double degree=static_cast<long double>(coefficients.size()-1-i);derivative=add_c(mul_c(derivative,z),scale_c(coefficients[i],degree));}}auto delta=div_c(value,derivative);if(!delta)return std::nullopt;z=sub_c(z,*delta);if(!finite_c(z))return std::nullopt;}return z;''',
        r'''if(coefficients.size()<2||!finite_c(start))return std::nullopt;C z=start;for(std::size_t i=0;i<steps;++i)z.real-=1.0L;return z;''',
        "auto r=ComplexNewtonIteration{}.iterate({{1,0},{0,0},{-1,0}},{2,0},1);return !r||!close(*r,{1.25L,0});",
        "auto x=ComplexNewtonIteration{};auto r=x.iterate({{1,0},{0,0},{-1,0}},{0,2},0);auto below=x.iterate({{1,0},{0,0},{1,0}},{2.5e-13L,0},1);auto at=x.iterate({{1,0},{0,0},{1,0}},{5e-13L,0},1);auto above=x.iterate({{1,0},{0,0},{1,0}},{1e-12L,0},1);return !r||!close(*r,{0,2})||x.iterate({{1,0}}, {1,0},1)||x.iterate({{0,0},{1,0}}, {0,0},1)||below||at||!above;",
        "Apply a bounded number of complex Newton steps using freshly evaluated polynomial and derivative values.",
        "Reject constant/empty polynomials, nonfinite values, more than 1000 steps, or a zero derivative.",
        "Zero steps returns the start; otherwise preserve sequential dependency between iterations.",
        "fixed-real-decrement", "struct ComplexValue { long double real; long double imag; };",
        "A complex divisor is zero when its squared magnitude is at most `1e-24L`; values just above that boundary remain admissible."))
    add(ArithmeticCase(
        "complex-dft-selected-bin", "Selected complex DFT bin", "complex",
        "direct negative-angle discrete Fourier accumulation for one bin",
        "std::optional<ComplexValue> bin(const std::vector<ComplexValue>& samples, std::size_t index) const",
        "std::optional<ComplexValue> {cls}::bin(const std::vector<ComplexValue>& samples, std::size_t index) const",
        r'''if(samples.empty()||index>=samples.size()||!all_finite(samples))return std::nullopt;const long double pi=std::acos(-1.0L);C sum{0,0};for(std::size_t n=0;n<samples.size();++n){long double angle=-2.0L*pi*static_cast<long double>(index*n)/static_cast<long double>(samples.size());sum=add_c(sum,mul_c(samples[n],{std::cos(angle),std::sin(angle)}));}return finite_c(sum)?std::optional<C>(sum):std::nullopt;''',
        r'''if(samples.empty()||index>=samples.size()||!all_finite(samples))return std::nullopt;C sum{0,0};for(C sample:samples)sum=add_c(sum,sample);return sum;''',
        "auto r=ComplexDftSelectedBin{}.bin({{1,0},{0,0},{-1,0},{0,0}},1);return !r||!close(*r,{2,0});",
        "auto x=ComplexDftSelectedBin{};auto r=x.bin({{1,0},{2,0}},0);return !r||!close(*r,{3,0})||x.bin({},0)||x.bin({{1,0}},1);",
        "Compute one requested negative-angle DFT bin by direct complex accumulation.",
        "Reject empty/nonfinite samples or an index outside the sample count.",
        "Sample order and bin index determine phase; the result is not normalized.",
        "bin-independent-sample-sum", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-linear-convolution", "Complex linear convolution", "complex",
        "full non-circular pairwise index-sum convolution",
        "std::optional<std::vector<ComplexValue>> convolve(const std::vector<ComplexValue>& left, const std::vector<ComplexValue>& right) const",
        "std::optional<std::vector<ComplexValue>> {cls}::convolve(const std::vector<ComplexValue>& left, const std::vector<ComplexValue>& right) const",
        r'''if(left.empty()||right.empty()||!all_finite(left)||!all_finite(right))return std::nullopt;std::vector<C> out(left.size()+right.size()-1,C{0,0});for(std::size_t i=0;i<left.size();++i)for(std::size_t j=0;j<right.size();++j){out[i+j]=add_c(out[i+j],mul_c(left[i],right[j]));if(!finite_c(out[i+j]))return std::nullopt;}return out;''',
        r'''if(left.empty()||right.empty()||!all_finite(left)||!all_finite(right))return std::nullopt;std::size_t n=std::min(left.size(),right.size());std::vector<C> out;for(std::size_t i=0;i<n;++i)out.push_back(mul_c(left[i],right[i]));return out;''',
        "auto r=ComplexLinearConvolution{}.convolve({{1,0},{1,0}},{{1,0},{0,1}});return !r||r->size()!=3||!close((*r)[1],{1,1})||!close((*r)[2],{0,1});",
        "auto x=ComplexLinearConvolution{};auto r=x.convolve({{2,1}},{{3,-1}});return !r||r->size()!=1||!close((*r)[0],{7,1})||x.convolve({},{{1,0}});",
        "Produce the full linear convolution of two complex sequences without circular wraparound.",
        "Reject empty/nonfinite inputs or nonfinite accumulation.",
        "Output index is the sum of source indices and length is m+n-1.",
        "pointwise-product", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-cross-correlation", "Complex cross-correlation", "complex",
        "lagged overlap sum with conjugation of the left sequence",
        "std::optional<ComplexValue> correlate(const std::vector<ComplexValue>& left, const std::vector<ComplexValue>& right, long long lag) const",
        "std::optional<ComplexValue> {cls}::correlate(const std::vector<ComplexValue>& left, const std::vector<ComplexValue>& right, long long lag) const",
        r'''if(!all_finite(left)||!all_finite(right)||lag==std::numeric_limits<long long>::min())return std::nullopt;C sum{0,0};for(std::size_t i=0;i<left.size();++i){long long j=static_cast<long long>(i)+lag;if(j>=0&&static_cast<std::size_t>(j)<right.size())sum=add_c(sum,mul_c(conj_c(left[i]),right[static_cast<std::size_t>(j)]));}return finite_c(sum)?std::optional<C>(sum):std::nullopt;''',
        r'''if(!all_finite(left)||!all_finite(right))return std::nullopt;C sum{0,0};for(std::size_t i=0;i<left.size();++i){long long j=static_cast<long long>(i)+lag;if(j>=0&&static_cast<std::size_t>(j)<right.size())sum=add_c(sum,mul_c(left[i],right[static_cast<std::size_t>(j)]));}return sum;''',
        "auto r=ComplexCrossCorrelation{}.correlate({{0,1}},{{0,1}},0);return !r||!close(*r,{1,0});",
        "auto x=ComplexCrossCorrelation{};auto r=x.correlate({{1,0}},{{2,0}},3);return !r||!close(*r,{0,0})||!x.correlate({}, {},0);",
        "Sum conjugated-left times lagged-right products over the valid overlap.",
        "Reject nonfinite inputs or an unrepresentable lag; an empty overlap returns zero.",
        "Preserve left index order and apply the signed lag before bounds selection.",
        "unconjugated-lag-product", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-impedance-reduction", "Complex impedance reduction", "complex",
        "postfix stack reduction with distinct series and reciprocal parallel operations",
        "std::optional<ComplexValue> reduce(const std::vector<ImpedanceToken>& postfix) const",
        "std::optional<ComplexValue> {cls}::reduce(const std::vector<ImpedanceToken>& postfix) const",
        r'''std::vector<C> stack;for(const auto&token:postfix){if(token.kind=='V'){if(!finite_c(token.value))return std::nullopt;stack.push_back(token.value);continue;}if((token.kind!='S'&&token.kind!='P')||stack.size()<2)return std::nullopt;C right=stack.back();stack.pop_back();C left=stack.back();stack.pop_back();if(token.kind=='S')stack.push_back(add_c(left,right));else{auto il=div_c({1,0},left),ir=div_c({1,0},right);auto result=il&&ir?div_c({1,0},add_c(*il,*ir)):std::nullopt;if(!result)return std::nullopt;stack.push_back(*result);}}if(stack.size()!=1||!finite_c(stack[0]))return std::nullopt;return stack[0];''',
        r'''C sum{0,0};for(const auto&token:postfix)if(token.kind=='V')sum=add_c(sum,token.value);return finite_c(sum)?std::optional<C>(sum):std::nullopt;''',
        "auto r=ComplexImpedanceReduction{}.reduce({{'V',{2,0}},{'V',{2,0}},{'P',{0,0}},{'V',{0,1}},{'S',{0,0}}});return !r||!close(*r,{1,1});",
        "auto x=ComplexImpedanceReduction{};auto r=x.reduce({{'V',{1,1}}});auto below=x.reduce({{'V',{5e-13L,0}},{'V',{1,0}},{'P',{0,0}}});auto at=x.reduce({{'V',{1e-12L,0}},{'V',{1,0}},{'P',{0,0}}});auto above=x.reduce({{'V',{2e-12L,0}},{'V',{1,0}},{'P',{0,0}}});return !r||!close(*r,{1,1})||x.reduce({{'S',{0,0}}})||x.reduce({{'V',{0,0}},{'V',{1,0}},{'P',{0,0}}})||below||at||!above;",
        "Reduce a postfix impedance expression using series addition and parallel reciprocal addition.",
        "Reject unknown tokens, stack underflow/residue, nonfinite values, or zero parallel denominators.",
        "Operands are popped right then left; series and parallel operators preserve postfix order.",
        "sum-all-components", "struct ComplexValue { long double real; long double imag; }; struct ImpedanceToken { char kind; ComplexValue value; };",
        "Every reciprocal divisor and reciprocal sum is zero when its squared magnitude is at most `1e-24L`; values just above that boundary are divided normally."))
    add(ArithmeticCase(
        "complex-phasor-prefix", "Complex phasor prefixes", "complex",
        "cumulative ordered complex multiplication with prefix emission",
        "std::optional<std::vector<ComplexValue>> prefixes(const std::vector<ComplexValue>& factors) const",
        "std::optional<std::vector<ComplexValue>> {cls}::prefixes(const std::vector<ComplexValue>& factors) const",
        r'''if(!all_finite(factors))return std::nullopt;std::vector<C> out;C current{1,0};for(C factor:factors){current=mul_c(current,factor);if(!finite_c(current))return std::nullopt;out.push_back(current);}return out;''',
        r'''if(!all_finite(factors))return std::nullopt;return factors;''',
        "auto r=ComplexPhasorPrefix{}.prefixes({{0,1},{0,1},{2,0}});return !r||r->size()!=3||!close((*r)[0],{0,1})||!close((*r)[1],{-1,0})||!close((*r)[2],{-2,0});",
        "auto x=ComplexPhasorPrefix{};auto r=x.prefixes({});return !r||!r->empty();",
        "Multiply phasors cumulatively from the identity and emit every ordered prefix product.",
        "Reject nonfinite factors or intermediate results; empty input returns an empty vector.",
        "Preserve factor order and emit after, not before, each multiplication.",
        "independent-factors", "struct ComplexValue { long double real; long double imag; };"))
    return tuple(rows)


def _complex_cases_second() -> tuple[ArithmeticCase, ...]:
    rows: list[ArithmeticCase] = []
    add = rows.append
    add(ArithmeticCase(
        "complex-mobius-transform", "Complex Mobius transform", "complex",
        "guarded fractional-linear transformation with nondegenerate coefficient determinant",
        "std::optional<ComplexValue> transform(ComplexValue z, ComplexValue a, ComplexValue b, ComplexValue c, ComplexValue d) const",
        "std::optional<ComplexValue> {cls}::transform(ComplexValue z, ComplexValue a, ComplexValue b, ComplexValue c, ComplexValue d) const",
        r'''if(!finite_c(z)||!finite_c(a)||!finite_c(b)||!finite_c(c)||!finite_c(d))return std::nullopt;C determinant=sub_c(mul_c(a,d),mul_c(b,c));if(norm_c(determinant)<=1e-24L)return std::nullopt;return div_c(add_c(mul_c(a,z),b),add_c(mul_c(c,z),d));''',
        r'''if(!finite_c(z)||!finite_c(a)||!finite_c(b))return std::nullopt;static_cast<void>(c);static_cast<void>(d);return add_c(mul_c(a,z),b);''',
        "auto r=ComplexMobiusTransform{}.transform({1,1},{1,0},{1,0},{0,0},{1,0});return !r||!close(*r,{2,1});",
        "auto x=ComplexMobiusTransform{};auto reciprocal=x.transform({2,0},{0,0},{1,0},{1,0},{0,0});auto det_below=x.transform({0,0},{5e-13L,0},{0,0},{0,0},{1,0});auto det_at=x.transform({0,0},{1e-12L,0},{0,0},{0,0},{1,0});auto det_above=x.transform({0,0},{2e-12L,0},{0,0},{0,0},{1,0});auto denominator_below=x.transform({0,0},{0,0},{-1,0},{1,0},{5e-13L,0});auto denominator_at=x.transform({0,0},{0,0},{-1,0},{1,0},{1e-12L,0});auto denominator_above=x.transform({0,0},{0,0},{-1,0},{1,0},{2e-12L,0});return !reciprocal||!close(*reciprocal,{0.5L,0})||x.transform({1,0},{1,0},{2,0},{2,0},{4,0})||x.transform({0,0},{1,0},{0,0},{1,0},{0,0})||det_below||det_at||!det_above||denominator_below||denominator_at||!denominator_above;",
        "Apply a nondegenerate complex fractional-linear transformation.",
        "Reject nonfinite input, zero coefficient determinant, or a zero denominator at z.",
        "Coefficient roles a,b,c,d are ordered and not interchangeable.",
        "affine-numerator-only", "struct ComplexValue { long double real; long double imag; };",
        "The coefficient determinant and the denominator at `z` are zero when squared magnitude is at most `1e-24L`; both must be strictly above that boundary."))
    add(ArithmeticCase(
        "complex-cross-ratio", "Ordered complex cross ratio", "complex",
        "ordered four-point product quotient",
        "std::optional<ComplexValue> ratio(ComplexValue z1, ComplexValue z2, ComplexValue z3, ComplexValue z4) const",
        "std::optional<ComplexValue> {cls}::ratio(ComplexValue z1, ComplexValue z2, ComplexValue z3, ComplexValue z4) const",
        r'''if(!finite_c(z1)||!finite_c(z2)||!finite_c(z3)||!finite_c(z4))return std::nullopt;C numerator=mul_c(sub_c(z1,z3),sub_c(z2,z4));C denominator=mul_c(sub_c(z1,z4),sub_c(z2,z3));return div_c(numerator,denominator);''',
        r'''if(!finite_c(z1)||!finite_c(z2)||!finite_c(z3)||!finite_c(z4))return std::nullopt;long double a=std::sqrt(norm_c(sub_c(z1,z3))),b=std::sqrt(norm_c(sub_c(z2,z4))),c=std::sqrt(norm_c(sub_c(z1,z4))),d=std::sqrt(norm_c(sub_c(z2,z3)));if(c*d<=1e-12L)return std::nullopt;return C{a*b/(c*d),0};''',
        "auto r=ComplexCrossRatio{}.ratio({0,0},{1,0},{0,1},{2,0});return !r||!close(*r,{0.25L,-0.25L});",
        "auto x=ComplexCrossRatio{};auto r=x.ratio({0,1},{1,0},{0,-1},{-1,0});auto below=x.ratio({0,0},{1,0},{0,0},{-5e-13L,0});auto at=x.ratio({0,0},{1,0},{0,0},{-1e-12L,0});auto above=x.ratio({0,0},{1,0},{0,0},{-2e-12L,0});return !r||!close(*r,{2,0})||x.ratio({0,0},{1,0},{2,0},{0,0})||below||at||!above;",
        "Compute the ordered complex cross ratio from two numerator and two denominator differences.",
        "Reject nonfinite points or a zero complex denominator.",
        "Argument order is observable; no distance magnitudes replace complex products.",
        "pairwise-distance-ratio", "struct ComplexValue { long double real; long double imag; };",
        "The complex denominator product is zero when its squared magnitude is at most `1e-24L`; a product just above that boundary is admissible."))
    add(ArithmeticCase(
        "complex-contour-integral", "Affine complex contour integral", "complex",
        "exact directed segment antiderivative accumulation for an affine complex field",
        "std::optional<ComplexValue> integrate(const std::vector<ComplexValue>& vertices, ComplexValue slope, ComplexValue intercept) const",
        "std::optional<ComplexValue> {cls}::integrate(const std::vector<ComplexValue>& vertices, ComplexValue slope, ComplexValue intercept) const",
        r'''if(vertices.size()<2||!all_finite(vertices)||!finite_c(slope)||!finite_c(intercept))return std::nullopt;C total{0,0};for(std::size_t i=0;i+1<vertices.size();++i){C a=vertices[i],b=vertices[i+1];C square_delta=sub_c(mul_c(b,b),mul_c(a,a));C linear_delta=sub_c(b,a);C term=add_c(scale_c(mul_c(slope,square_delta),0.5L),mul_c(intercept,linear_delta));total=add_c(total,term);if(!finite_c(total))return std::nullopt;}return total;''',
        r'''if(vertices.size()<2||!all_finite(vertices)||!finite_c(slope)||!finite_c(intercept))return std::nullopt;C total{0,0};for(std::size_t i=0;i+1<vertices.size();++i)total=add_c(total,mul_c(add_c(mul_c(slope,vertices[i]),intercept),sub_c(vertices[i+1],vertices[i])));return total;''',
        "auto r=ComplexContourIntegral{}.integrate({{0,0},{2,0}},{1,0},{0,0});return !r||!close(*r,{2,0});",
        "auto x=ComplexContourIntegral{};auto r=x.integrate({{2,1},{2,1},{3,1}},{0,0},{1,0});return !r||!close(*r,{1,0})||x.integrate({{0,0}},{1,0},{0,0});",
        "Integrate slope*z+intercept exactly along each directed straight segment.",
        "Reject fewer than two vertices or nonfinite values; zero-length segments contribute zero.",
        "Preserve vertex order and do not implicitly close the path.",
        "left-endpoint-field-sampling", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-matrix-determinant", "Complex matrix determinant", "complex",
        "largest-magnitude pivot elimination with complex row factors and swap parity",
        "std::optional<ComplexValue> determinant(std::vector<std::vector<ComplexValue>> matrix) const",
        "std::optional<ComplexValue> {cls}::determinant(std::vector<std::vector<ComplexValue>> matrix) const",
        r'''std::size_t n=matrix.size();if(n==0)return C{1,0};for(const auto&row:matrix)if(row.size()!=n||!all_finite(row))return std::nullopt;C det{1,0};int sign=1;for(std::size_t col=0;col<n;++col){std::size_t pivot=col;for(std::size_t row=col+1;row<n;++row)if(norm_c(matrix[row][col])>norm_c(matrix[pivot][col]))pivot=row;if(norm_c(matrix[pivot][col])<=1e-24L)return C{0,0};if(pivot!=col){std::swap(matrix[pivot],matrix[col]);sign=-sign;}C p=matrix[col][col];det=mul_c(det,p);for(std::size_t row=col+1;row<n;++row){auto factor=div_c(matrix[row][col],p);if(!factor)return std::nullopt;for(std::size_t j=col;j<n;++j)matrix[row][j]=sub_c(matrix[row][j],mul_c(*factor,matrix[col][j]));}}if(sign<0)det=scale_c(det,-1);return finite_c(det)?std::optional<C>(det):std::nullopt;''',
        r'''if(matrix.empty())return C{1,0};C result{1,0};for(std::size_t i=0;i<matrix.size();++i){if(matrix[i].size()!=matrix.size())return std::nullopt;result=mul_c(result,matrix[i][i]);}return result;''',
        "auto r=ComplexMatrixDeterminant{}.determinant({{{1,1},{2,0}},{{0,1},{3,-1}}});return !r||!close(*r,{4,0});",
        "auto x=ComplexMatrixDeterminant{};auto r=x.determinant({{{0,0},{1,0}},{{2,0},{3,0}}});auto z=x.determinant({{{1,0},{2,0}},{{2,0},{4,0}}});auto e=x.determinant({});auto below=x.determinant({{{5e-13L,0}}});auto at=x.determinant({{{1e-12L,0}}});auto above=x.determinant({{{2e-12L,0}}});return !r||!close(*r,{-2,0})||!z||!close(*z,{0,0})||!e||!close(*e,{1,0})||!below||below->real!=0||!at||at->real!=0||!above||above->real<=0;",
        "Compute a complex square-matrix determinant through magnitude-pivoted elimination.",
        "Reject ragged, nonsquare, or nonfinite matrices; singular returns zero and empty returns one.",
        "Choose the largest squared-magnitude pivot and apply row-swap parity.",
        "diagonal-product", "struct ComplexValue { long double real; long double imag; };",
        "A pivot with squared magnitude at most `1e-24L` is treated as zero; that makes the determinant singular zero rather than a rejected input."))
    add(ArithmeticCase(
        "complex-linear-system", "Complex linear system", "complex",
        "largest-magnitude pivot Gauss-Jordan solution",
        "std::optional<std::vector<ComplexValue>> solve(std::vector<std::vector<ComplexValue>> matrix, std::vector<ComplexValue> rhs) const",
        "std::optional<std::vector<ComplexValue>> {cls}::solve(std::vector<std::vector<ComplexValue>> matrix, std::vector<ComplexValue> rhs) const",
        r'''std::size_t n=matrix.size();if(n==0||rhs.size()!=n||!all_finite(rhs))return std::nullopt;for(const auto&row:matrix)if(row.size()!=n||!all_finite(row))return std::nullopt;for(std::size_t col=0;col<n;++col){std::size_t pivot=col;for(std::size_t row=col+1;row<n;++row)if(norm_c(matrix[row][col])>norm_c(matrix[pivot][col]))pivot=row;if(norm_c(matrix[pivot][col])<=1e-24L)return std::nullopt;if(pivot!=col){std::swap(matrix[pivot],matrix[col]);std::swap(rhs[pivot],rhs[col]);}C p=matrix[col][col];for(std::size_t j=0;j<n;++j){auto v=div_c(matrix[col][j],p);if(!v)return std::nullopt;matrix[col][j]=*v;}auto rv=div_c(rhs[col],p);if(!rv)return std::nullopt;rhs[col]=*rv;for(std::size_t row=0;row<n;++row){if(row==col)continue;C factor=matrix[row][col];for(std::size_t j=0;j<n;++j){matrix[row][j]=sub_c(matrix[row][j],mul_c(factor,matrix[col][j]));}rhs[row]=sub_c(rhs[row],mul_c(factor,rhs[col]));}}return all_finite(rhs)?std::optional<std::vector<C>>(rhs):std::nullopt;''',
        r'''std::size_t n=matrix.size();if(n==0||rhs.size()!=n)return std::nullopt;std::vector<C> out;for(std::size_t i=0;i<n;++i){if(matrix[i].size()!=n)return std::nullopt;auto v=div_c(rhs[i],matrix[i][i]);if(!v)return std::nullopt;out.push_back(*v);}return out;''',
        "auto r=ComplexLinearSystem{}.solve({{{1,0},{1,0}},{{0,1},{1,0}}},{{3,1},{1,3}});return !r||!close((*r)[0],{2,0})||!close((*r)[1],{1,1});",
        "auto x=ComplexLinearSystem{};auto r=x.solve({{{0,0},{1,0}},{{1,0},{1,0}}},{{2,0},{3,0}});auto below=x.solve({{{5e-13L,0}}},{{5e-13L,0}});auto at=x.solve({{{1e-12L,0}}},{{1e-12L,0}});auto above=x.solve({{{2e-12L,0}}},{{2e-12L,0}});return !r||!close((*r)[0],{1,0})||!close((*r)[1],{2,0})||x.solve({{{1,0},{2,0}},{{2,0},{4,0}}},{{1,0},{2,0}})||below||at||!above||!close((*above)[0],{1,0});",
        "Solve a nonempty complex square system through magnitude-pivoted Gauss-Jordan elimination.",
        "Reject dimension mismatch, singularity, nonfinite input, or nonfinite intermediate.",
        "Return variables by column order after eliminating every nonpivot row.",
        "diagonal-only-solve", "struct ComplexValue { long double real; long double imag; };",
        "A pivot or complex divisor with squared magnitude at most `1e-24L` is zero and makes the system singular; pivots just above it are admissible."))
    add(ArithmeticCase(
        "complex-quantum-gate", "Two-state complex gate", "complex",
        "row-major two-by-two gate application with norm-preservation admission",
        "std::optional<std::vector<ComplexValue>> apply(const std::vector<ComplexValue>& gate, const std::vector<ComplexValue>& state) const",
        "std::optional<std::vector<ComplexValue>> {cls}::apply(const std::vector<ComplexValue>& gate, const std::vector<ComplexValue>& state) const",
        r'''if(gate.size()!=4||state.size()!=2||!all_finite(gate)||!all_finite(state))return std::nullopt;long double input=norm_c(state[0])+norm_c(state[1]);if(std::fabs(input-1.0L)>1e-10L)return std::nullopt;std::vector<C> out={add_c(mul_c(gate[0],state[0]),mul_c(gate[1],state[1])),add_c(mul_c(gate[2],state[0]),mul_c(gate[3],state[1]))};long double output=norm_c(out[0])+norm_c(out[1]);if(!all_finite(out)||std::fabs(output-input)>1e-10L)return std::nullopt;return out;''',
        r'''if(gate.size()!=4||state.size()!=2)return std::nullopt;return std::vector<C>{mul_c(gate[0],state[0]),mul_c(gate[3],state[1])};''',
        "auto r=ComplexQuantumGate{}.apply({{0,0},{1,0},{1,0},{0,0}},{{1,0},{0,0}});return !r||!close((*r)[0],{0,0})||!close((*r)[1],{1,0});",
        "auto x=ComplexQuantumGate{};long double s=std::sqrt(0.5L);auto r=x.apply({{s,0},{s,0},{s,0},{-s,0}},{{0,0},{1,0}});long double below_component=std::sqrt(5e-11L);long double boundary_component=0.0L,boundary_high=std::sqrt(2e-10L);for(int iteration=0;iteration<100;++iteration){long double middle=(boundary_component+boundary_high)/2.0L;long double deviation=(1.0L+middle*middle)-1.0L;if(deviation<=1e-10L)boundary_component=middle;else boundary_high=middle;}long double above_component=std::sqrt(2e-10L);auto state_below=x.apply({{1,0},{0,0},{0,0},{1,0}},{{1,0},{below_component,0}});auto state_at=x.apply({{1,0},{0,0},{0,0},{1,0}},{{1,0},{boundary_component,0}});auto state_above=x.apply({{1,0},{0,0},{0,0},{1,0}},{{1,0},{above_component,0}});auto output_below=x.apply({{1,0},{0,0},{below_component,0},{1,0}},{{1,0},{0,0}});auto output_at=x.apply({{1,0},{0,0},{boundary_component,0},{1,0}},{{1,0},{0,0}});auto output_above=x.apply({{1,0},{0,0},{above_component,0},{1,0}},{{1,0},{0,0}});return !r||!close((*r)[0],{s,0})||!close((*r)[1],{-s,0})||x.apply({{1,0},{0,0},{0,0},{2,0}},{{0,0},{1,0}}).has_value()||!state_below||!state_at||state_above||!output_below||!output_at||output_above;",
        "Apply a row-major two-by-two complex gate to two normalized amplitudes.",
        "Reject wrong lengths, nonfinite/non-normalized state, or a gate result that changes total norm.",
        "Both output rows combine both input amplitudes and output order is row order.",
        "diagonal-only-gate", "struct ComplexValue { long double real; long double imag; };",
        "The input squared-norm deviation from one and the output-vs-input squared-norm deviation may each be at most `1e-10L`; a larger deviation is rejected."))
    add(ArithmeticCase(
        "complex-state-normalization", "Complex state normalization", "complex",
        "unit-norm scaling followed by canonical global-phase rotation",
        "std::optional<std::vector<ComplexValue>> normalize(const std::vector<ComplexValue>& state) const",
        "std::optional<std::vector<ComplexValue>> {cls}::normalize(const std::vector<ComplexValue>& state) const",
        r'''if(state.empty()||!all_finite(state))return std::nullopt;long double squared=0;for(C value:state)squared+=norm_c(value);if(!std::isfinite(squared)||squared<=1e-24L)return std::nullopt;long double magnitude=std::sqrt(squared);std::vector<C> out;for(C value:state){out.push_back(scale_c(value,1.0L/magnitude));}std::size_t first=0;while(first<out.size()&&norm_c(out[first])<=1e-24L)++first;if(first==out.size())return std::nullopt;long double phase=std::atan2(out[first].imag,out[first].real);C rotation{std::cos(-phase),std::sin(-phase)};for(C&value:out)value=mul_c(value,rotation);if(out[first].real<0)for(C&value:out)value=scale_c(value,-1);return all_finite(out)?std::optional<std::vector<C>>(out):std::nullopt;''',
        r'''if(state.empty()||!all_finite(state))return std::nullopt;long double squared=0;for(C value:state)squared+=norm_c(value);if(squared<=1e-24L)return std::nullopt;std::vector<C> out;for(C value:state)out.push_back(scale_c(value,1/std::sqrt(squared)));return out;''',
        "auto r=ComplexStateNormalization{}.normalize({{0,0},{0,2},{0,0}});return !r||!close((*r)[1],{1,0});",
        "auto x=ComplexStateNormalization{};auto r=x.normalize({{-1,-1},{1,1}});long double s=std::sqrt(0.5L);auto below=x.normalize({{5e-13L,0}});auto at=x.normalize({{1e-12L,0}});auto above=x.normalize({{2e-12L,0}});return !r||!close((*r)[0],{s,0})||x.normalize({{0,0}})||x.normalize({})||below||at||!above||!close((*above)[0],{1,0});",
        "Scale a nonzero complex vector to unit norm and remove its global phase canonically.",
        "Reject empty, all-zero, nonfinite, or nonfinite-normalization input.",
        "Preserve component order and make the first nonzero component real and nonnegative.",
        "magnitude-only-scaling", "struct ComplexValue { long double real; long double imag; };",
        "The total squared norm and each candidate first nonzero component use `1e-24L` as an inclusive zero boundary; a component must be strictly above it."))
    add(ArithmeticCase(
        "complex-bilinear-surface", "Complex bilinear surface", "complex",
        "ordered two-axis interpolation over four complex corners",
        "std::optional<ComplexValue> interpolate(ComplexValue c00, ComplexValue c10, ComplexValue c01, ComplexValue c11, long double u, long double v) const",
        "std::optional<ComplexValue> {cls}::interpolate(ComplexValue c00, ComplexValue c10, ComplexValue c01, ComplexValue c11, long double u, long double v) const",
        r'''if(!finite_c(c00)||!finite_c(c10)||!finite_c(c01)||!finite_c(c11)||!std::isfinite(u)||!std::isfinite(v)||u<0||u>1||v<0||v>1)return std::nullopt;C lower=add_c(scale_c(c00,1-u),scale_c(c10,u));C upper=add_c(scale_c(c01,1-u),scale_c(c11,u));C result=add_c(scale_c(lower,1-v),scale_c(upper,v));return finite_c(result)?std::optional<C>(result):std::nullopt;''',
        r'''if(!finite_c(c00)||!finite_c(c10)||!finite_c(c01)||!finite_c(c11))return std::nullopt;static_cast<void>(u);static_cast<void>(v);return scale_c(add_c(add_c(c00,c10),add_c(c01,c11)),0.25L);''',
        "auto r=ComplexBilinearSurface{}.interpolate({0,0},{2,0},{0,2},{2,2},0.25L,0.75L);return !r||!close(*r,{0.5L,1.5L});",
        "auto x=ComplexBilinearSurface{};auto r=x.interpolate({1,2},{3,4},{5,6},{7,8},1,0);return !r||!close(*r,{3,4})||x.interpolate({0,0},{0,0},{0,0},{0,0},-0.1L,0);",
        "Interpolate the x direction on both rows, then interpolate those results in y.",
        "Reject nonfinite corners/parameters or u/v outside the closed unit interval.",
        "Corner order is c00,c10,c01,c11 and boundary parameters select exact edges.",
        "four-corner-average", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-roots-unity-filter", "Roots-of-unity filter", "complex",
        "indexed roots-of-unity spectral accumulation",
        "std::optional<ComplexValue> sum(std::size_t order, const std::vector<std::size_t>& indices) const",
        "std::optional<ComplexValue> {cls}::sum(std::size_t order, const std::vector<std::size_t>& indices) const",
        r'''if(order==0||order>4096)return std::nullopt;const long double pi=std::acos(-1.0L);C result{0,0};for(std::size_t index:indices){if(index>=order)return std::nullopt;long double angle=2*pi*static_cast<long double>(index)/static_cast<long double>(order);result=add_c(result,{std::cos(angle),std::sin(angle)});}return finite_c(result)?std::optional<C>(result):std::nullopt;''',
        r'''if(order==0||order>4096)return std::nullopt;for(std::size_t index:indices)if(index>=order)return std::nullopt;return C{static_cast<long double>(indices.size()),0};''',
        "auto r=ComplexRootsUnityFilter{}.sum(4,{0,1,2,3});return !r||!close(*r,{0,0});",
        "auto x=ComplexRootsUnityFilter{};auto r=x.sum(3,{0,0});return !r||!close(*r,{2,0})||x.sum(0,{})||x.sum(3,{3});",
        "Accumulate the requested indexed roots of unity with positive angular orientation.",
        "Reject order outside 1..4096 or any index at least order; duplicate indices are valid.",
        "Preserve supplied index order and count duplicates as repeated spectral contributions.",
        "selected-index-count", "struct ComplexValue { long double real; long double imag; };"))
    add(ArithmeticCase(
        "complex-mandelbrot-escape", "Mandelbrot escape iteration", "complex",
        "guarded quadratic orbit with first-escape reporting",
        "std::optional<int> escape(ComplexValue c, int max_iterations, long double bailout_squared) const",
        "std::optional<int> {cls}::escape(ComplexValue c, int max_iterations, long double bailout_squared) const",
        r'''if(!finite_c(c)||max_iterations<0||max_iterations>1000000||!std::isfinite(bailout_squared)||bailout_squared<=1)return std::nullopt;C z{0,0};for(int iteration=1;iteration<=max_iterations;++iteration){z=add_c(mul_c(z,z),c);long double squared=norm_c(z);if(!std::isfinite(squared))return std::nullopt;if(squared>bailout_squared)return iteration;}return 0;''',
        r'''if(!finite_c(c)||max_iterations<0||!std::isfinite(bailout_squared)||bailout_squared<=1)return std::nullopt;static_cast<void>(max_iterations);return norm_c(c)>bailout_squared?1:0;''',
        "auto r=ComplexMandelbrotEscape{}.escape({2,0},20,4);return !r||*r!=2;",
        "auto x=ComplexMandelbrotEscape{};auto inside=x.escape({0,0},100,4);auto zero=x.escape({3,0},0,4);return !inside||*inside!=0||!zero||*zero!=0||x.escape({0,0},-1,4)||x.escape({0,0},5,1);",
        "Iterate z = z*z + c from zero and report the first one-based escape iteration.",
        "Reject nonfinite c/bailout, bailout at most one, or iterations outside 0..1,000,000.",
        "Zero iterations returns zero and nonescaping points return zero after the full bound.",
        "single-step-magnitude-test", "struct ComplexValue { long double real; long double imag; };"))
    return tuple(rows)


COMPLEX_CASES = _complex_cases_first() + _complex_cases_second()
TASKS = RATIONAL_CASES + COMPLEX_CASES

if len(RATIONAL_CASES) != 20 or len(COMPLEX_CASES) != 20 or len(TASKS) != 40:
    raise AssertionError("the binding rational/complex count cell requires 20+20 tasks")
if len({case.task_id for case in TASKS}) != 40:
    raise AssertionError("task IDs must be unique")
