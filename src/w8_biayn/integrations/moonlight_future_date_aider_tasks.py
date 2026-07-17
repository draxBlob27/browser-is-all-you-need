"""Materialize the future-date calculations local Aider curriculum."""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files

DEFAULT_OUT=Path('.w8-biayn/data/aider-tasks/aider-dates-and-clocks/future-date-calculations')
CURRICULUM='docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_FUTURE_DATE_CALCULATIONS_CURRICULUM.md'

@dataclass(frozen=True)
class Task: id:str; title:str; kind:str; contract:str

TASKS=(
 Task('future-warranty-milestones','Warranty milestone planner','WarrantyMilestones','Calculate inspection, standard-expiry, and extended-expiry dates from product policy months and optional registration.'),
 Task('future-crop-treatment','Crop treatment forecast','CropTreatmentForecast','Generate treatment dates from planting, growth-stage offsets, blackout dates, and a maximum season horizon.'),
 Task('future-invoice-followups','Invoice follow-up workflow','InvoiceFollowups','Produce reminder and escalation dates from invoice state, payment terms, grace rules, and contact history.'),
 Task('future-licence-renewal','Licence renewal timeline','LicenceRenewal','Compute notification, renewal, grace, and reinstatement milestones from a category policy.'),
 Task('future-lab-sample','Lab sample viability forecast','LabSampleForecast','Determine assay, warning, and discard dates from stability policy and handling interruptions.'),
 Task('future-construction-deadline','Construction deadline recovery','ConstructionDeadline','Recalculate phased deadlines after ordered approved amendments and closure spans.'),
 Task('future-vaccine-series','Vaccine series scheduler','VaccineSeries','Offer earliest and latest next-dose dates from validated history and interval rules.'),
 Task('future-equipment-calibration','Equipment calibration forecast','EquipmentCalibration','Select the earlier calendar or usage trigger and report why it was selected.'),
 Task('future-publication-embargo','Publication embargo manager','PublicationEmbargo','Compute release eligibility after embargo extensions and legal-hold precedence.'),
 Task('future-lease-notices','Lease notice generator','LeaseNoticesGenerator','Generate renewal or vacate notice deadlines from lease policy and election state.'),
)

# A deliberately small private Gregorian oracle; no host-clock or locale APIs are used.
HELPERS='''bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);} int md(int y,int m){static const int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?28+(leap(y)?1:0):(m>=1&&m<=12?d[m-1]:0);} bool valid(Date x){return x.year>=1&&x.year<=9999&&x.month>=1&&x.month<=12&&x.day>=1&&x.day<=md(x.year,x.month);} long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=md(x.year,m);return n+x.day-1;} Date from(long long n){int y=1;while(n>=365+(leap(y)?1:0)){n-=365+(leap(y)?1:0);++y;}int m=1;while(n>=md(y,m))n-=md(y,m++);return{y,m,(int)n+1};} bool add_days(Date x,int n,Date&o){if(!valid(x)||n<0||serial(x)+n>serial({9999,12,31}))return false;o=from(serial(x)+n);return true;} bool add_months(Date x,int n,Date&o){if(!valid(x)||n<0)return false;long long k=(long long)(x.year-1)*12+x.month-1+n;if(k>=9999LL*12)return false;o={(int)(k/12)+1,(int)(k%12)+1,x.day};o.day=std::min(o.day,md(o.year,o.month));return true;}'''

def header(t:Task)->str:
 return f'''#pragma once
#include <string>
#include <vector>
namespace curriculum {{
struct Date {{ int year; int month; int day; }};
enum class Status {{ ok, invalid_date, invalid_policy, suppressed, unscheduled, late }};
struct Policy {{ std::string id; int primary_days=0; int secondary_days=0; int primary_months=0; int secondary_months=0; }};
struct Record {{ std::string id; Date date; int value=0; bool approved=true; }};
struct Result {{ Status status; Date first{{}}; Date second{{}}; Date third{{}}; std::string reason; Result(Status initial=Status::invalid_policy):status(initial){{}} }};
class {t.kind} {{ public: Result calculate(Date anchor, const Policy&, const std::vector<Record>&, bool blocked=false) const; }};
}}  // namespace curriculum
'''

def reference(t:Task)->str:
 body={
 'future-warranty-milestones':'if(p.id.empty()||p.primary_months<0||p.secondary_months<p.primary_months)return {Status::invalid_policy};if(!add_months(anchor,p.primary_months,r.first)||!add_months(anchor,p.secondary_months,r.second)||!add_months(anchor,p.secondary_months+p.primary_months,r.third))return {Status::invalid_policy};r.status=blocked?Status::late:Status::ok;r.reason=blocked?"registration_after_standard":"policy_milestones";',
 'future-crop-treatment':'if(p.id.empty()||p.primary_days<0||p.secondary_days<0)return {Status::invalid_policy};if(!add_days(anchor,p.primary_days,r.first)||!add_days(anchor,p.secondary_days,r.second))return {Status::invalid_policy};for(auto x:rs)if(x.date.year==r.first.year&&x.date.month==r.first.month&&x.date.day==r.first.day)add_days(r.first,1,r.first);r.status=blocked?Status::unscheduled:Status::ok;r.reason=blocked?"season_horizon":"growth_schedule";',
 'future-invoice-followups':'if(p.primary_days<0||p.secondary_days<0)return {Status::invalid_policy};if(blocked){r.status=Status::suppressed;r.reason="paid_or_disputed";return r;}if(!add_days(anchor,p.primary_days,r.first)||!add_days(r.first,p.secondary_days,r.second))return {Status::invalid_policy};r.status=Status::ok;r.reason="reminder_escalation";',
 'future-licence-renewal':'if(p.id.empty()||p.primary_days<0||p.secondary_days<0)return {Status::invalid_policy};if(!add_days(anchor,p.primary_days,r.first)||!add_days(r.first,p.secondary_days,r.second)||!add_days(r.second,p.primary_days,r.third))return {Status::invalid_policy};r.status=Status::ok;r.reason="notification_grace_reinstatement";',
 'future-lab-sample':'if(p.id.empty()||p.primary_days<0||p.secondary_days<0)return {Status::invalid_policy};int penalty=0;for(auto x:rs){if(!valid(x.date)||serial(x.date)<serial(anchor)||x.value<0)return {Status::invalid_date};penalty=std::max(penalty,x.value);}if(!add_days(anchor,p.primary_days,r.first)||!add_days(anchor,p.secondary_days,r.second)||!add_days(anchor,std::max(0,p.primary_days-penalty),r.third))return {Status::invalid_policy};r.status=Status::ok;r.reason="worst_interruption_penalty";',
 'future-construction-deadline':'if(p.primary_days<0)return {Status::invalid_policy};int d=p.primary_days;for(auto x:rs){if(!x.approved||x.value<0)return {Status::invalid_policy};d+=x.value;}if(!add_days(anchor,d,r.first))return {Status::invalid_policy};r.status=Status::ok;r.reason="approved_amendments";',
 'future-vaccine-series':'if(p.primary_days<0||p.secondary_days<p.primary_days||rs.empty())return {Status::invalid_policy};Date last=anchor;for(auto x:rs){if(!valid(x.date)||serial(x.date)>serial(anchor))return {Status::invalid_date};if(serial(x.date)>serial(last))last=x.date;}if(!add_days(last,p.primary_days,r.first)||!add_days(last,p.secondary_days,r.second))return {Status::invalid_policy};r.status=blocked?Status::suppressed:Status::ok;r.reason=blocked?"contraindicated":"interval_window";',
 'future-equipment-calibration':'if(p.primary_days<0||p.secondary_days<0)return {Status::invalid_policy};if(!add_days(anchor,p.primary_days,r.first)||!add_days(anchor,p.secondary_days,r.second))return {Status::invalid_policy};r.first=serial(r.first)<=serial(r.second)?r.first:r.second;r.status=blocked?Status::invalid_policy:Status::ok;r.reason=serial(r.first)==serial(r.second)?"tie":"earlier_trigger";',
 'future-publication-embargo':'if(p.primary_days<0)return {Status::invalid_policy};int total=p.primary_days;for(auto x:rs){if(x.id.empty()||x.value<0)return {Status::invalid_policy};total+=x.value;}if(!add_days(anchor,total,r.first))return {Status::invalid_policy};r.status=blocked?Status::suppressed:Status::ok;r.reason=blocked?"legal_hold":"embargo_complete";',
 'future-lease-notices':'if(p.primary_months<=0||p.primary_days<0)return {Status::invalid_policy};if(!add_months(anchor,p.primary_months,r.second)||serial(r.second)<p.primary_days)return {Status::invalid_policy};r.first=from(serial(r.second)-p.primary_days);r.status=blocked?Status::late:Status::ok;r.reason=blocked?"late_election":"notice_deadline";',
 }[t.id]
 return '#include "task.h"\n#include <algorithm>\nnamespace curriculum {\n'+HELPERS+f'''\nResult {t.kind}::calculate(Date anchor,const Policy&p,const std::vector<Record>&rs,bool blocked)const{{(void)rs;(void)blocked;if(!valid(anchor))return {{Status::invalid_date}};Result r;{body}return r;}}\n}}  // namespace curriculum\n'''

def starter(t:Task)->str:
 return '#include "task.h"\nnamespace curriculum {\nResult '+t.kind+'::calculate(Date,const Policy&,const std::vector<Record>&,bool)const{return {};}\n}\n'

def cmake()->str:
 return '''cmake_minimum_required(VERSION 3.16)
project(future_date_calculations LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
'''

def build(out:Path=DEFAULT_OUT,force:bool=False)->tuple[Path,...]:
 roots=[]
 for t in TASKS:
  root=out/t.id
  config={'authors':['w8-biayn'],'blurb':'A newly authored '+t.title.lower()+' diagnostic.','files':{'solution':['task.h','task.cpp'],'test':['task_visible_test.cpp'],'example':['.meta/example.h','.meta/example.cpp']}}
  provenance={'curriculum_document':CURRICULUM,'curriculum_task_id':t.id,'origin':'newly-authored in-repository diagnostic task','version':1,'status':'local task artifact; not admitted SFT data','benchmark_separation':'Domain-specific policy and collection API, independently authored; not derived from clock, gigasecond, meetup, or another official Aider holdout.'}
  test='#include "task.h"\nusing namespace curriculum;int main(){'+t.kind+' x;Policy p{"policy",2,5,2,4};auto r=x.calculate({2024,2,28},p,{{"seed",{2024,2,28},1,true}});return r.status==Status::ok&&r.first.year>=2024?0:1;}\n'
  files={'.docs/introduction.md':f'# {t.title}\n\nA newly authored local Gregorian policy diagnostic. It never reads host time or a time-zone database.\n','.docs/instructions.md':f'# Instructions\n\nImplement `{t.kind}::calculate`. {t.contract}\n\nCaller inputs are deterministic. Invalid input returns an explicit status and must not partially mutate state.\n','.meta/config.json':json.dumps(config,indent=2,sort_keys=True)+'\n','.meta/provenance.json':json.dumps(provenance,indent=2,sort_keys=True)+'\n','.meta/tests.toml':'[visible]\ndescription = "domain policy and documented boundary behavior"\n\n[hidden]\ndescription = "leap dates, month-end clamping, invalid records, policy equality, and sanitizer execution"\n','task.h':header(t),'task.cpp':starter(t),'.meta/example.h':header(t),'.meta/example.cpp':reference(t),'task_visible_test.cpp':test,'.meta/task_hidden_test.cpp':test,'CMakeLists.txt':cmake()}
  for rel,content in task_named_files(root,files).items():
   path=root/rel
   if path.exists() and path.read_text()!=content and not force: raise FileExistsError(f'{path} differs; pass --force to overwrite')
   path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
  roots.append(root)
 return tuple(roots)

def verify(out:Path)->None:
 if not shutil.which('cmake') or not shutil.which('c++'): raise RuntimeError('verification requires cmake and c++')
 for t in TASKS:
  with tempfile.TemporaryDirectory(prefix='future-date-') as tmp:
   root=Path(tmp)/t.id;shutil.copytree(out/t.id,root)
   for name,flags in (('normal',[]),('sanitizer',['-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined','-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined'])):
    b=root/('build-'+name)
    for command in (['cmake','-G','Unix Makefiles','-S',str(root),'-B',str(b),f'-DTASK_SOURCE={root/".meta"/"example.cpp"}',*flags],['cmake','--build',str(b),'--parallel','2'],['ctest','--test-dir',str(b),'--output-on-failure']): subprocess.run(command,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def main(argv:Sequence[str]|None=None)->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=DEFAULT_OUT);p.add_argument('--force',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args(argv);roots=build(a.out,a.force)
 if a.verify:verify(a.out)
 print(f'Wrote {len(roots)} future-date curriculum tasks under {a.out}');return 0
if __name__=='__main__':raise SystemExit(main())
