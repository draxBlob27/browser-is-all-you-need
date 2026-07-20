from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    disposition: str
    title: str
    objective: str
    types: str
    return_type: str
    function: str
    params: str
    body: str
    visible: str
    hidden: str
    negative_old: str
    negative_new: str
    negative_description: str
    prompt_terms: tuple[str, ...]
    profile: tuple[str, ...]


CASES = (
    Case(
        "pattern-archway-stones", "pattern-archway-stones", "repair-in-place",
        "Archway voussoir raster", "rasterizing a discrete semicircular arch by squared distance bands",
        "struct ArchReport { std::vector<std::string> rows; std::size_t stones = 0; std::size_t keystone_column = 0; bool valid = false; };",
        "ArchReport", "raster_archway", "std::size_t radius, char stone",
        r'''if (radius < 2 || radius > 30 || stone == ' ') return {};
ArchReport out; out.valid = true; out.keystone_column = radius; const std::size_t side = 2 * radius + 1;
out.rows.assign(radius + 1, std::string(side, ' '));
const long outer = static_cast<long>(radius * radius); const long inner = static_cast<long>((radius - 1) * (radius - 1));
for (std::size_t row = 0; row <= radius; ++row) for (std::size_t col = 0; col < side; ++col) {
  const long x = static_cast<long>(col) - static_cast<long>(radius); const long y = static_cast<long>(radius - row); const long d = x * x + y * y;
  if (d <= outer && d >= inner) { out.rows[row][col] = stone; ++out.stones; }
}
return out;''',
        r'''auto z = raster_archway(2, '#'); return !(z.valid && z.rows == std::vector<std::string>{"  #  ", " ### ", "## ##"} && z.keystone_column == 2 && z.stones == 8);''',
        r'''auto z = raster_archway(3, 'K'); if (!z.valid || z.rows.size() != 4 || z.rows.front()[3] != 'K' || z.rows.back().front() != 'K' || z.rows.back().back() != 'K') return 1; return raster_archway(1, '#').valid || raster_archway(31, '#').valid || raster_archway(3, ' ').valid;''',
        "d <= outer", "d < outer", "an open outer-radius comparison drops required voussoirs",
        ("squared distance", "inner radius", "outer radius", "keystone"),
        ("semicircle-band", "distance-raster", "radius-validation", "keystone-index"),
    ),
    Case(
        "pattern-theater-seating", "seat-band-capacity-chart", "replace",
        "Seat-band capacity chart", "laying out variable-capacity seating bands around a fixed center aisle",
        "struct SeatBand { char section = ' '; std::size_t seats = 0; }; struct SeatingChart { std::vector<std::string> rows; std::size_t vacant = 0; bool valid = false; };",
        "SeatingChart", "render_seat_bands", "const std::vector<SeatBand>& bands, std::size_t occupied",
        r'''if (bands.empty()) return {}; std::size_t width = 0, capacity = 0; for (const auto& band : bands) { if (band.section == ' ' || band.seats < 2) return {}; width = std::max(width, band.seats + 1); capacity += band.seats; } if (occupied > capacity) return {};
SeatingChart out; out.valid = true; out.vacant = capacity - occupied;
for (const auto& band : bands) { const std::size_t left = band.seats / 2; std::string row; row.append(left, band.section); row.push_back('|'); row.append(band.seats - left, band.section); const std::size_t pad = width - row.size(); out.rows.push_back(std::string(pad / 2, ' ') + row + std::string(pad - pad / 2, ' ')); }
return out;''',
        r'''auto z = render_seat_bands({{'A',4},{'B',2}}, 3); return !(z.valid && z.rows == std::vector<std::string>{"AA|AA", " B|B "} && z.vacant == 3);''',
        r'''auto z = render_seat_bands({{'X',3}}, 0); if (!z.valid || z.rows != std::vector<std::string>{"X|XX"} || z.vacant != 3) return 1; return render_seat_bands({},0).valid || render_seat_bands({{' ',2}},0).valid || render_seat_bands({{'A',2}},3).valid;''',
        "const std::size_t left = band.seats / 2", "const std::size_t left = 0", "a one-sided band omits the documented center split",
        ("center aisle", "band capacity", "occupied", "vacant"),
        ("variable-row-width", "center-divider", "capacity-ledger", "stable-band-order"),
    ),
    Case(
        "pattern-ski-trail-sign", "ski-chevron-route-sign", "replace",
        "Ski chevron route sign", "drawing alternating left/right route chevrons with an explicit legend row",
        "enum class Turn { left, right }; struct TrailSign { std::vector<std::string> rows; std::size_t turns = 0; bool valid = false; };",
        "TrailSign", "render_trail_sign", "const std::vector<Turn>& route, char difficulty",
        r'''if (route.empty() || difficulty == ' ') return {}; TrailSign out; out.valid = true; const std::size_t width = 2 * route.size() + 1;
for (std::size_t i = 0; i < route.size(); ++i) { std::string row(width, ' '); const std::size_t center = route.size(); const std::size_t col = route[i] == Turn::left ? center - i : center + i; row[col] = route[i] == Turn::left ? '<' : '>'; row[center] = difficulty; out.rows.push_back(row); }
out.rows.push_back(std::string(width, '=') + " " + difficulty); out.turns = route.size(); return out;''',
        r'''auto z = render_trail_sign({Turn::left,Turn::right}, 'B'); return !(z.valid && z.rows == std::vector<std::string>{"  B  ", "  B> ", "===== B"} && z.turns == 2);''',
        r'''auto z = render_trail_sign({Turn::right,Turn::left,Turn::right}, 'D'); if (!z.valid || z.rows.size()!=4 || z.rows[2][5]!='>' || z.rows.back().substr(0,7)!="=======") return 1; return render_trail_sign({},'A').valid || render_trail_sign({Turn::left},' ').valid;''',
        "center + i", "center", "right turns must advance away from the centerline",
        ("chevron", "route order", "difficulty legend", "centerline"),
        ("direction-sequence", "signed-offset", "legend-row", "turn-count"),
    ),
    Case(
        "pattern-roof-trusses", "roof-truss-bay-lattice", "replace",
        "Roof-truss bay lattice", "constructing repeated triangular bays with shared posts and a load ledger",
        "struct TrussPlan { std::vector<std::string> rows; std::vector<std::size_t> joint_columns; std::size_t joints = 0; bool valid = false; };",
        "TrussPlan", "draft_truss_lattice", "std::size_t bays, std::size_t load_per_joint",
        r'''if (bays == 0 || bays > 20 || load_per_joint == 0) return {}; TrussPlan out; out.valid = true; const std::size_t width = 4 * bays + 1; out.rows.assign(3, std::string(width, ' '));
for (std::size_t bay = 0; bay < bays; ++bay) { const std::size_t base = 4 * bay; out.rows[0][base + 2] = '^'; out.rows[1][base + 1] = '/'; out.rows[1][base + 3] = '\\'; out.joint_columns.push_back(base + 2); for (std::size_t c = base; c <= base + 4; ++c) out.rows[2][c] = '_'; }
out.joint_columns.push_back(width - 1);
out.joints = (2 * bays + 1) * load_per_joint; return out;''',
        r'''auto z = draft_truss_lattice(2,3); return !(z.valid && z.rows == std::vector<std::string>{"  ^   ^  ", " / \\ / \\ ", "_________"} && z.joint_columns == std::vector<std::size_t>{2,6,8} && z.joints == 15);''',
        r'''auto z=draft_truss_lattice(1,2); if(!z.valid||z.rows[0]!="  ^  "||z.joint_columns!=std::vector<std::size_t>{2,4}||z.joints!=6) return 1; return draft_truss_lattice(0,2).valid||draft_truss_lattice(21,2).valid||draft_truss_lattice(2,0).valid;''',
        "(2 * bays + 1) * load_per_joint", "2 * bays * load_per_joint", "the joint ledger must include the shared terminal post",
        ("triangular bay", "shared post", "load per joint", "base chord"),
        ("repeated-cell-composition", "shared-boundary", "three-layer-lattice", "load-ledger"),
    ),
    Case(
        "pattern-festival-bunting", "cyclic-pennant-bunting", "replace",
        "Cyclic pennant bunting", "rasterizing variable-height pennants from a cyclic symbol palette",
        "struct BuntingPlan { std::vector<std::string> rows; std::vector<std::size_t> tassel_columns; bool valid = false; };",
        "BuntingPlan", "hang_cyclic_pennants", "const std::string& palette, std::size_t pennants, std::size_t height",
        r'''if (palette.empty() || pennants == 0 || height < 2 || height > 12) return {}; const std::size_t pitch = 2 * height - 1; BuntingPlan out; out.valid = true; out.rows.assign(height, std::string(pennants * pitch, ' '));
for (std::size_t p=0;p<pennants;++p) for(std::size_t r=0;r<height;++r){const std::size_t span=pitch-2*r; const std::size_t left=p*pitch+r; std::fill_n(out.rows[r].begin()+static_cast<std::ptrdiff_t>(left),span,palette[p%palette.size()]); if(r+1==height) out.tassel_columns.push_back(left);}
return out;''',
        r'''auto z=hang_cyclic_pennants("AB",2,2); return !(z.valid&&z.rows==std::vector<std::string>{"AAABBB"," A  B "}&&z.tassel_columns==std::vector<std::size_t>{1,4});''',
        r'''auto z=hang_cyclic_pennants("XYZ",1,3); if(!z.valid||z.rows!=std::vector<std::string>{"XXXXX"," XXX ","  X  "}) return 1; return hang_cyclic_pennants("",2,3).valid||hang_cyclic_pennants("A",0,3).valid||hang_cyclic_pennants("A",2,1).valid;''',
        "pitch-2*r", "pitch-r", "each pennant must taper by one cell on both edges",
        ("palette cycle", "pennant pitch", "taper", "tassel column"),
        ("triangular-fill", "cyclic-symbol", "row-span", "tip-coordinate"),
    ),
    Case(
        "pattern-orchard-canopy", "orchard-canopy-union", "replace",
        "Orchard canopy union", "forming a union of Manhattan-radius tree canopies and counting overlaps",
        "struct Tree { std::size_t row=0; std::size_t col=0; }; struct CanopyReport { std::vector<std::string> rows; std::size_t overlap_cells=0; bool valid=false; };",
        "CanopyReport", "render_canopy_union", "std::size_t rows, std::size_t cols, const std::vector<Tree>& trees, std::size_t radius",
        r'''if(rows==0||cols==0||trees.empty()||radius==0) return {}; for(const auto& t:trees) if(t.row>=rows||t.col>=cols) return {}; CanopyReport out; out.valid=true; out.rows.assign(rows,std::string(cols,'.'));
for(std::size_t r=0;r<rows;++r) for(std::size_t c=0;c<cols;++c){std::size_t covers=0; for(const auto& t:trees){const std::size_t d=(r>t.row?r-t.row:t.row-r)+(c>t.col?c-t.col:t.col-c); covers+=d<=radius;} if(covers){out.rows[r][c]=covers>1?'@':'o'; if(covers>1) ++out.overlap_cells;}}
return out;''',
        r'''auto z=render_canopy_union(3,5,{{1,1},{1,3}},1); return !(z.valid&&z.rows==std::vector<std::string>{".o.o.","oo@oo",".o.o."}&&z.overlap_cells==1);''',
        r'''auto z=render_canopy_union(1,3,{{0,0}},2); if(!z.valid||z.rows!=std::vector<std::string>{"ooo"}) return 1; return render_canopy_union(0,2,{{0,0}},1).valid||render_canopy_union(2,2,{},1).valid||render_canopy_union(2,2,{{2,0}},1).valid;''',
        "covers+=d<=radius", "covers+=d<radius", "the closed canopy radius must include its boundary",
        ("Manhattan radius", "canopy union", "overlap", "tree coordinate"),
        ("multi-source-coverage", "diamond-neighborhood", "overlap-count", "dense-raster"),
    ),
    Case(
        "pattern-signal-cones", "striped-cone-stencil", "replace",
        "Striped cone stencil", "drawing cone edges while filling periodic safety-stripe rows",
        "struct ConeStencil { std::vector<std::string> rows; std::size_t stripe_cells=0; bool valid=false; };",
        "ConeStencil", "render_cone_stencil", "std::size_t height, std::size_t stripe_period, char stripe",
        r'''if(height<2||height>30||stripe_period==0||stripe==' ') return {}; ConeStencil out; out.valid=true; const std::size_t width=2*height-1;
for(std::size_t r=0;r<height;++r){std::string row(width,' '); const std::size_t left=height-1-r,right=height-1+r; row[left]='/'; row[right]='\\'; if(r%stripe_period==0){for(std::size_t c=left;c<=right;++c){row[c]=stripe;++out.stripe_cells;}} out.rows.push_back(row);} return out;''',
        r'''auto z=render_cone_stencil(3,2,'='); return !(z.valid&&z.rows==std::vector<std::string>{"  =  "," / \\ ","====="}&&z.stripe_cells==6);''',
        r'''auto z=render_cone_stencil(2,3,'#'); if(!z.valid||z.rows!=std::vector<std::string>{" # ","/ \\"}||z.stripe_cells!=1) return 1; return render_cone_stencil(1,1,'#').valid||render_cone_stencil(3,0,'#').valid||render_cone_stencil(3,1,' ').valid;''',
        "r%stripe_period==0", "(r+1)%stripe_period==0", "stripe cadence is anchored at the cone tip",
        ("edge stencil", "stripe period", "tip anchored", "stripe cells"),
        ("outline-and-fill", "periodic-row", "closed-span", "cell-ledger"),
    ),
    Case(
        "pattern-tournament-bracket", "elimination-bracket-connectors", "replace",
        "Elimination bracket connectors", "placing power-of-two seeds and round connectors in a sparse bracket grid",
        "struct BracketBoard { std::vector<std::string> rows; std::size_t rounds=0; bool valid=false; };",
        "BracketBoard", "render_elimination_bracket", "const std::vector<char>& seeds",
        r'''if(seeds.size()<2||(seeds.size()&(seeds.size()-1))!=0) return {}; for(char s:seeds) if(s==' ') return {}; std::size_t rounds=0; for(std::size_t n=seeds.size();n>1;n/=2) ++rounds; BracketBoard out; out.valid=true; out.rounds=rounds; out.rows.assign(2*seeds.size()-1,std::string(3*rounds+1,' '));
for(std::size_t i=0;i<seeds.size();++i) out.rows[2*i][0]=seeds[i]; for(std::size_t round=0;round<rounds;++round){const std::size_t step=static_cast<std::size_t>(1)<<round; for(std::size_t first=0;first<seeds.size();first+=2*step){const std::size_t top=2*first+step-1,bottom=2*(first+2*step-1)-step+1,mid=(top+bottom)/2; for(std::size_t r=top;r<=bottom;++r) out.rows[r][3*round+2]='|'; out.rows[mid][3*round+3]='-';}}
return out;''',
        r'''auto z=render_elimination_bracket({'A','B'}); return !(z.valid&&z.rounds==1&&z.rows==std::vector<std::string>{"A | ","  |-","B | "});''',
        r'''auto z=render_elimination_bracket({'A','B','C','D'}); if(!z.valid||z.rounds!=2||z.rows.size()!=7||z.rows[3][5]!='|'||z.rows[3][6]!='-') return 1; return render_elimination_bracket({'A'}).valid||render_elimination_bracket({'A',' ','C','D'}).valid||render_elimination_bracket({'A','B','C'}).valid;''',
        "out.rounds=rounds", "out.rounds=0", "the report must expose the computed elimination depth",
        ("power of two", "round connector", "seed row", "elimination depth"),
        ("sparse-bracket", "doubling-step", "connector-column", "round-count"),
    ),
    Case(
        "pattern-mountain-profile", "ridge-height-silhouette", "replace",
        "Ridge-height silhouette", "rasterizing a height profile with exposed ridge and filled rock cells",
        "struct RidgeProfile { std::vector<std::string> rows; std::size_t exposed_edges=0; bool valid=false; };",
        "RidgeProfile", "render_ridge_profile", "const std::vector<std::size_t>& heights, std::size_t ceiling",
        r'''if(heights.empty()||ceiling==0) return {}; for(auto h:heights) if(h>ceiling) return {}; RidgeProfile out; out.valid=true; out.rows.assign(ceiling,std::string(heights.size(),' '));
for(std::size_t c=0;c<heights.size();++c) for(std::size_t level=0;level<heights[c];++level){const std::size_t r=ceiling-1-level; const bool exposed=level+1==heights[c]; out.rows[r][c]=exposed?'^':'#'; if(exposed) ++out.exposed_edges;} return out;''',
        r'''auto z=render_ridge_profile({1,3,2},3); return !(z.valid&&z.rows==std::vector<std::string>{" ^ "," #^","^##"}&&z.exposed_edges==3);''',
        r'''auto z=render_ridge_profile({0,2},2); if(!z.valid||z.rows!=std::vector<std::string>{" ^"," #"}||z.exposed_edges!=1) return 1; return render_ridge_profile({},2).valid||render_ridge_profile({3},2).valid||render_ridge_profile({1},0).valid;''',
        "level+1==heights[c]", "level==0", "the exposed marker belongs at each column summit",
        ("height profile", "summit", "ceiling", "rock fill"),
        ("column-raster", "top-surface", "bottom-alignment", "edge-count"),
    ),
    Case(
        "pattern-lighthouse-beam", "occluded-lighthouse-fan", "replace",
        "Occluded lighthouse fan", "casting integer-slope beam rays that stop at obstacle cells",
        "struct Obstacle { std::size_t row=0; std::size_t col=0; }; struct BeamFrame { std::vector<std::string> rows; std::vector<std::size_t> occluded_targets; std::size_t lit=0; bool valid=false; };",
        "BeamFrame", "cast_lighthouse_fan", "std::size_t height, std::size_t width, std::size_t tower_col, const std::vector<Obstacle>& obstacles",
        r'''if(height<2||width<3||tower_col>=width) return {}; std::set<std::pair<std::size_t,std::size_t>> blocked; for(const auto& o:obstacles) if(o.row>=height||o.col>=width||!blocked.insert({o.row,o.col}).second) return {}; BeamFrame out; out.valid=true; out.rows.assign(height,std::string(width,'.')); out.rows[height-1][tower_col]='T';
for(std::size_t target=0;target<width;++target){for(std::size_t step=1;step<height;++step){const std::size_t row=height-1-step; const long delta=static_cast<long>(target)-static_cast<long>(tower_col); const long col=static_cast<long>(tower_col)+(delta*static_cast<long>(step))/static_cast<long>(height-1); const auto key=std::make_pair(row,static_cast<std::size_t>(col)); if(blocked.count(key)){out.rows[row][key.second]='X';out.occluded_targets.push_back(target);break;} if(out.rows[row][key.second]=='.'){out.rows[row][key.second]='*';++out.lit;}}}
return out;''',
        r'''auto z=cast_lighthouse_fan(3,3,1,{{1,1}}); return !(z.valid&&z.rows==std::vector<std::string>{"...",".X.",".T."}&&z.occluded_targets==std::vector<std::size_t>{0,1,2}&&z.lit==0);''',
        r'''auto z=cast_lighthouse_fan(2,3,1,{}); if(!z.valid||z.rows[0]!="***"||!z.occluded_targets.empty()||z.lit!=3) return 1; return cast_lighthouse_fan(1,3,1,{}).valid||cast_lighthouse_fan(3,3,3,{}).valid||cast_lighthouse_fan(3,3,1,{{0,0},{0,0}}).valid;''',
        "if(blocked.count(key))", "if(false)", "a beam must terminate on its first obstacle",
        ("ray", "integer slope", "occlusion", "tower column"),
        ("ray-casting", "first-hit-stop", "deduplicated-raster", "light-count"),
    ),
    Case(
        "pattern-quilt-medallion", "concentric-quilt-rings", "replace",
        "Concentric quilt rings", "assigning rectangular ring distance to a cyclic palette",
        "struct PaletteCell { char symbol=' '; std::size_t cells=0; }; struct MedallionReport { std::vector<std::string> rows; std::vector<PaletteCell> palette; bool valid=false; };",
        "MedallionReport", "weave_quilt_rings", "std::size_t rows, std::size_t cols, const std::string& palette",
        r'''if(rows==0||cols==0||palette.empty()) return {}; std::set<char> unique; for(char p:palette) if(p==' '||!unique.insert(p).second) return {}; MedallionReport out; out.valid=true; out.rows.assign(rows,std::string(cols,' ')); std::map<char,std::size_t> counts;
for(std::size_t r=0;r<rows;++r) for(std::size_t c=0;c<cols;++c){const std::size_t ring=std::min(std::min(r,rows-1-r),std::min(c,cols-1-c)); const char symbol=palette[ring%palette.size()]; out.rows[r][c]=symbol; ++counts[symbol];} for(char p:palette) out.palette.push_back({p,counts[p]}); return out;''',
        r'''auto z=weave_quilt_rings(3,5,"AB"); return !(z.valid&&z.rows==std::vector<std::string>{"AAAAA","ABBBA","AAAAA"}&&z.palette[0].cells==12&&z.palette[1].cells==3);''',
        r'''auto z=weave_quilt_rings(1,2,"XY"); if(!z.valid||z.rows!=std::vector<std::string>{"XX"}||z.palette.size()!=2) return 1; return weave_quilt_rings(0,2,"A").valid||weave_quilt_rings(2,2,"").valid||weave_quilt_rings(2,2,"AA").valid;''',
        "ring%palette.size()", "(ring+1)%palette.size()", "the outer ring must begin at palette index zero",
        ("rectangular ring", "cyclic palette", "cell histogram", "inset distance"),
        ("distance-transform", "concentric-fill", "ordered-histogram", "palette-cycle"),
    ),
    Case(
        "pattern-pyramid-crates", "labeled-crate-pyramid", "replace",
        "Labeled crate pyramid", "centering token-aware crate labels in bottom-wide tiers",
        "struct CrateStack { std::vector<std::string> rows; std::size_t byte_width=0; bool valid=false; };",
        "CrateStack", "stack_labeled_crates", "const std::vector<std::string>& labels",
        r'''if(labels.empty()) return {}; std::size_t cell=0; for(const auto& label:labels){if(label.empty()||label.size()>6) return {}; cell=std::max(cell,label.size());} const std::size_t levels=labels.size(); CrateStack out; out.valid=true; out.byte_width=levels*(cell+3)-1;
for(std::size_t r=0;r<levels;++r){const std::size_t count=r+1,pad=(levels-count)*(cell+3)/2; std::string row(pad,' '); for(std::size_t k=0;k<count;++k){if(k) row.push_back(' '); const auto& label=labels[(r+k)%labels.size()]; row.push_back('['); row+=label; row.append(cell-label.size(),' '); row.push_back(']');} row.append(out.byte_width-row.size(),' '); out.rows.push_back(row);} return out;''',
        r'''auto z=stack_labeled_crates({"1","22"}); return !(z.valid&&z.byte_width==9&&z.rows==std::vector<std::string>{"  [1 ]   ","[22] [1 ]"});''',
        r'''auto z=stack_labeled_crates({"A"}); if(!z.valid||z.rows!=std::vector<std::string>{"[A]"}||z.byte_width!=3) return 1; return stack_labeled_crates({}).valid||stack_labeled_crates({""}).valid||stack_labeled_crates({"1234567"}).valid;''',
        "labels[(r+k)%labels.size()]", "labels[k%labels.size()]", "tier label rotation must include the current row offset",
        ("token width", "tier", "bracketed crate", "right padding"),
        ("token-aware-layout", "triangular-count", "rotating-label", "fixed-byte-width"),
    ),
    Case(
        "pattern-garden-trellis", "blocked-trellis-vines", "replace",
        "Blocked trellis vines", "weaving two diagonal vine phases while preserving blocked lattice cells",
        "struct Cell { std::size_t row=0; std::size_t col=0; }; struct TrellisView { std::vector<std::string> rows; std::vector<Cell> crossing_cells; std::size_t crossings=0; bool valid=false; };",
        "TrellisView", "weave_trellis_vines", "std::size_t rows, std::size_t cols, std::size_t spacing, const std::vector<Cell>& blocked",
        r'''if(rows==0||cols==0||spacing<2) return {}; std::set<std::pair<std::size_t,std::size_t>> stops; for(const auto& b:blocked) if(b.row>=rows||b.col>=cols||!stops.insert({b.row,b.col}).second) return {}; TrellisView out; out.valid=true; out.rows.assign(rows,std::string(cols,'.'));
for(std::size_t r=0;r<rows;++r) for(std::size_t c=0;c<cols;++c){if(stops.count({r,c})){out.rows[r][c]='#';continue;} const bool down=(r+c)%spacing==0,up=(r+cols-1-c)%spacing==0; out.rows[r][c]=down&&up?'X':(down?'\\':(up?'/':'.')); if(down&&up){out.crossing_cells.push_back({r,c});++out.crossings;}} return out;''',
        r'''auto z=weave_trellis_vines(2,3,2,{{0,1}}); return !(z.valid&&z.rows==std::vector<std::string>{"X#X",".X."}&&z.crossing_cells.size()==3&&z.crossing_cells[0].row==0&&z.crossing_cells[0].col==0&&z.crossing_cells[2].row==1&&z.crossing_cells[2].col==1&&z.crossings==3);''',
        r'''auto z=weave_trellis_vines(1,1,2,{}); if(!z.valid||z.rows!=std::vector<std::string>{"X"}||z.crossing_cells.size()!=1||z.crossing_cells[0].row!=0||z.crossing_cells[0].col!=0||z.crossings!=1) return 1; return weave_trellis_vines(0,2,2,{}).valid||weave_trellis_vines(2,2,1,{}).valid||weave_trellis_vines(2,2,2,{{0,0},{0,0}}).valid;''',
        "if(stops.count({r,c}))", "if(false)", "blocked trellis cells must remain authoritative",
        ("diagonal phase", "blocked cell", "crossing", "spacing"),
        ("modular-weave", "two-phase-overlay", "obstacle-preservation", "crossing-count"),
    ),
    Case(
        "pattern-snowflake-banner", "eight-ray-snowflake-banner", "replace",
        "Eight-ray snowflake banner", "drawing axial and diagonal rays around a caller-selected center token",
        "struct BannerReport { std::vector<std::string> rows; std::size_t arm_cells=0; bool valid=false; };",
        "BannerReport", "render_snowflake_banner", "std::size_t radius, char center, char arm",
        r'''if(radius==0||radius>20||center==' '||arm==' '||center==arm) return {}; const std::size_t side=2*radius+1; BannerReport out; out.valid=true; out.rows.assign(side,std::string(side,' '));
for(std::size_t r=0;r<side;++r) for(std::size_t c=0;c<side;++c){const std::size_t dr=r>radius?r-radius:radius-r,dc=c>radius?c-radius:radius-c; if(r==radius&&c==radius) out.rows[r][c]=center; else if(r==radius||c==radius||dr==dc){out.rows[r][c]=arm;++out.arm_cells;}} return out;''',
        r'''auto z=render_snowflake_banner(1,'O','*'); return !(z.valid&&z.rows==std::vector<std::string>{"***","*O*","***"}&&z.arm_cells==8);''',
        r'''auto z=render_snowflake_banner(2,'C','+'); if(!z.valid||z.rows.size()!=5||z.rows[2][2]!='C'||z.arm_cells!=16) return 1; return render_snowflake_banner(0,'C','+').valid||render_snowflake_banner(2,' ','+').valid||render_snowflake_banner(2,'C','C').valid;''',
        "dr==dc", "dr+dc==radius", "diagonal arms must extend from the center to all four corners",
        ("eight rays", "center token", "axial", "diagonal"),
        ("axis-overlay", "diagonal-overlay", "odd-square", "arm-ledger"),
    ),
    Case(
        "pattern-warehouse-stacks", "warehouse-aisle-run-map", "replace",
        "Warehouse aisle run map", "placing non-overlapping stock runs into fixed-width aisles and reporting empty aisles",
        "struct StockRun { std::size_t aisle=0; std::size_t begin=0; std::size_t length=0; char symbol=' '; }; struct StockMap { std::vector<std::string> rows; std::vector<std::size_t> empty_aisles; std::size_t occupied=0; bool valid=false; };",
        "StockMap", "render_stock_aisles", "std::size_t aisle_count, std::size_t aisle_width, const std::vector<StockRun>& runs",
        r'''if(aisle_count==0||aisle_width==0) return {}; StockMap out; out.rows.assign(aisle_count,std::string(aisle_width,'.')); std::vector<bool> used(aisle_count,false);
for(const auto& run:runs){if(run.aisle>=aisle_count||run.length==0||run.begin>=aisle_width||run.length>aisle_width-run.begin||run.symbol==' '||run.symbol=='.') return {}; for(std::size_t c=run.begin;c<run.begin+run.length;++c){if(out.rows[run.aisle][c]!='.') return {}; out.rows[run.aisle][c]=run.symbol;++out.occupied;} used[run.aisle]=true;}
for(std::size_t aisle=0;aisle<aisle_count;++aisle) if(!used[aisle]) out.empty_aisles.push_back(aisle); out.valid=true; return out;''',
        r'''auto z=render_stock_aisles(3,5,{{0,1,2,'A'},{2,0,3,'B'}}); if(!(z.valid&&z.rows==std::vector<std::string>{".AA..",".....","BBB.."}&&z.empty_aisles==std::vector<std::size_t>{1}&&z.occupied==5)) return 1; return render_stock_aisles(1,4,{{0,0,3,'X'},{0,2,2,'Y'}}).valid;''',
        r'''auto z=render_stock_aisles(2,3,{}); if(!z.valid||z.rows!=std::vector<std::string>{"...","..."}||z.empty_aisles!=std::vector<std::size_t>{0,1}||z.occupied!=0) return 1; return render_stock_aisles(0,3,{}).valid||render_stock_aisles(2,0,{}).valid||render_stock_aisles(2,3,{{2,0,1,'A'}}).valid||render_stock_aisles(2,3,{{0,2,2,'A'}}).valid||render_stock_aisles(2,3,{{0,0,1,'.'}}).valid;''',
        "if(out.rows[run.aisle][c]!='.')", "if(false)", "overlapping stock runs must be rejected before a cell is overwritten",
        ("aisle run", "non-overlap", "empty aisle", "occupied cell"),
        ("interval-placement", "collision-rejection", "row-occupancy", "empty-row-ledger"),
    ),
    Case(
        "pattern-launch-countdown", "seven-segment-countdown-strip", "replace",
        "Seven-segment countdown strip", "composing fixed five-row glyphs for a descending digit sequence",
        "struct CountdownBoard { std::vector<std::string> rows; std::size_t digits=0; bool valid=false; };",
        "CountdownBoard", "render_countdown_strip", "unsigned start, unsigned stop",
        r'''if(start>9||stop>start) return {}; const std::vector<std::vector<std::string>> glyphs={{{" _ ","| |","| |","| |","|_|"}},{{"   ","  |","  |","  |","  |"}},{{" _ ","  |"," _|","|  ","|_ "}},{{" _ ","  |"," _|","  |"," _|"}},{{"   ","| |","|_|","  |","  |"}},{{" _ ","|  ","|_ ","  |"," _|"}},{{" _ ","|  ","|_ ","| |","|_|"}},{{" _ ","  |","  |","  |","  |"}},{{" _ ","| |","|_|","| |","|_|"}},{{" _ ","| |","|_|","  |"," _|"}}}; CountdownBoard out; out.valid=true; out.digits=start-stop+1; out.rows.assign(5,"");
for(unsigned value=start;;--value){for(std::size_t r=0;r<5;++r){if(!out.rows[r].empty()) out.rows[r].push_back(' ');out.rows[r]+=glyphs[value][r];}if(value==stop)break;} return out;''',
        r'''auto z=render_countdown_strip(1,0); return !(z.valid&&z.digits==2&&z.rows[0]=="     _ "&&z.rows[4]=="  | |_|" );''',
        r'''auto z=render_countdown_strip(2,2); if(!z.valid||z.digits!=1||z.rows[2]!=" _|") return 1; return render_countdown_strip(10,0).valid||render_countdown_strip(2,3).valid;''',
        "out.digits=start-stop+1", "out.digits=1", "the board must count every glyph in the inclusive descending range",
        ("seven segment", "descending", "inclusive stop", "glyph separator"),
        ("glyph-composition", "lookup-table", "descending-loop", "fixed-height"),
    ),
    Case(
        "pattern-choir-riser", "choir-riser-voice-allocation", "replace",
        "Choir riser voice allocation", "filling staggered risers from ordered voice-part counts",
        "struct VoicePart { char symbol=' '; std::size_t singers=0; }; struct RiserChart { std::vector<std::string> rows; std::size_t unplaced=0; bool valid=false; };",
        "RiserChart", "assign_choir_risers", "const std::vector<std::size_t>& capacities, const std::vector<VoicePart>& voices",
        r'''if(capacities.empty()||voices.empty()) return {}; std::size_t seats=0,singers=0; for(auto c:capacities){if(c==0)return {};seats+=c;} for(const auto& v:voices){if(v.symbol==' '||v.singers==0)return {};singers+=v.singers;} RiserChart out; out.valid=true; out.unplaced=singers>seats?singers-seats:0; std::size_t voice=0,remaining=voices[0].singers;
for(auto cap:capacities){std::string row; for(std::size_t seat=0;seat<cap;++seat){if(voice>=voices.size())row.push_back('.');else{row.push_back(voices[voice].symbol);if(--remaining==0){++voice;if(voice<voices.size())remaining=voices[voice].singers;}}} out.rows.push_back(row);} return out;''',
        r'''auto z=assign_choir_risers({2,3},{{'S',3},{'A',1}}); return !(z.valid&&z.rows==std::vector<std::string>{"SS","SA."}&&z.unplaced==0);''',
        r'''auto z=assign_choir_risers({1},{{'B',2}}); if(!z.valid||z.rows!=std::vector<std::string>{"B"}||z.unplaced!=1) return 1; return assign_choir_risers({},{{'A',1}}).valid||assign_choir_risers({1},{}).valid||assign_choir_risers({0},{{'A',1}}).valid;''',
        "row.push_back('.')", "row.push_back('?')", "vacant riser positions must use the declared dot marker",
        ("riser capacity", "voice order", "unplaced", "vacant dot"),
        ("run-consumption", "ragged-capacity", "ordered-allocation", "overflow-ledger"),
    ),
    Case(
        "pattern-harbor-beacons", "harbor-beacon-cadence", "replace",
        "Harbor beacon cadence", "merging independent periodic flashes around an open channel",
        "struct BeaconFrame { std::vector<std::string> rows; std::size_t simultaneous=0; bool valid=false; };",
        "BeaconFrame", "render_beacon_cadence", "std::size_t ticks, std::size_t left_period, std::size_t right_period, std::size_t channel_width",
        r'''if(ticks==0||left_period==0||right_period==0||channel_width==0) return {}; BeaconFrame out; out.valid=true;
for(std::size_t t=0;t<ticks;++t){const bool left=t%left_period==0,right=t%right_period==0; std::string row; row.push_back(left?'*':'.'); row.append(channel_width,'~'); row.push_back(right?'*':'.'); out.rows.push_back(row); out.simultaneous+=left&&right;} return out;''',
        r'''auto z=render_beacon_cadence(4,2,3,2); return !(z.valid&&z.rows==std::vector<std::string>{"*~~*",".~~.","*~~.",".~~*"}&&z.simultaneous==1);''',
        r'''auto z=render_beacon_cadence(1,5,7,1); if(!z.valid||z.rows!=std::vector<std::string>{"*~*"}||z.simultaneous!=1) return 1; return render_beacon_cadence(0,1,1,1).valid||render_beacon_cadence(2,0,1,1).valid||render_beacon_cadence(2,1,1,0).valid;''',
        "out.simultaneous+=left&&right", "out.simultaneous+=left||right", "simultaneous counts require both beacons on the same tick",
        ("period", "tick zero", "channel", "simultaneous"),
        ("dual-modular-stream", "time-rows", "fixed-gap", "coincidence-count"),
    ),
    Case(
        "pattern-ice-rink-lines", "ice-rink-zone-overlay", "replace",
        "Ice-rink zone overlay", "overlaying boards, blue lines, center line, and faceoff spots in precedence order",
        "struct RinkDiagram { std::vector<std::string> rows; std::vector<std::size_t> zone_columns; std::string zone_labels; std::size_t faceoff_spots=0; bool valid=false; };",
        "RinkDiagram", "render_rink_zones", "std::size_t interior_rows, std::size_t interior_cols",
        r'''if(interior_rows<3||interior_cols<9||interior_cols%2==0) return {}; const std::size_t rows=interior_rows+2,cols=interior_cols+2; RinkDiagram out; out.valid=true; out.rows.assign(rows,std::string(cols,' ')); for(std::size_t r=0;r<rows;++r)for(std::size_t c=0;c<cols;++c)if(r==0||c==0||r+1==rows||c+1==cols)out.rows[r][c]='#';
const std::size_t blue1=1+interior_cols/3,blue2=1+2*interior_cols/3,center=1+interior_cols/2; out.zone_columns={blue1,center,blue2}; out.zone_labels="BCB"; for(std::size_t r=1;r+1<rows;++r){out.rows[r][blue1]='B';out.rows[r][blue2]='B';out.rows[r][center]='C';} for(std::size_t r: {std::size_t{1},interior_rows}) for(std::size_t c:{blue1,blue2}){out.rows[r][c]='o';++out.faceoff_spots;} return out;''',
        r'''auto z=render_rink_zones(3,9); return !(z.valid&&z.rows.size()==5&&z.rows[2]=="#   BC B  #"&&z.zone_columns==std::vector<std::size_t>{4,5,7}&&z.zone_labels=="BCB"&&z.faceoff_spots==4);''',
        r'''auto z=render_rink_zones(4,11); if(!z.valid||z.rows.front()!=std::string(13,'#')||z.zone_columns!=std::vector<std::size_t>{4,6,8}||z.zone_labels!="BCB"||z.faceoff_spots!=4) return 1; return render_rink_zones(2,9).valid||render_rink_zones(3,8).valid||render_rink_zones(3,7).valid;''',
        "out.rows[r][center]='C'", "out.rows[r][center]='B'", "the center line must remain distinct from blue-line overlays",
        ("boards", "blue line", "center line", "faceoff precedence"),
        ("layered-overlay", "fractional-columns", "border-frame", "spot-count"),
    ),
    Case(
        "pattern-cave-supports", "cave-brace-triangulation", "replace",
        "Cave brace triangulation", "placing alternating diagonal braces between evenly spaced roof anchors",
        "struct SupportPlan { std::vector<std::string> rows; std::vector<std::size_t> anchors; bool valid=false; };",
        "SupportPlan", "triangulate_cave_braces", "std::size_t width, std::size_t height, std::size_t spacing",
        r'''if(width<3||height<2||spacing<2||spacing>=width) return {}; SupportPlan out; out.valid=true; out.rows.assign(height,std::string(width,' ')); for(std::size_t c=0;c<width;c+=spacing){out.rows[0][c]='+';out.anchors.push_back(c);} if(out.anchors.back()!=width-1){out.rows[0][width-1]='+';out.anchors.push_back(width-1);} for(std::size_t i=0;i+1<out.anchors.size();++i){const std::size_t left=out.anchors[i],right=out.anchors[i+1],span=right-left; for(std::size_t r=1;r<height;++r){const std::size_t offset=std::min(span,(r*span)/(height-1)); const std::size_t c=i%2==0?left+offset:right-offset; out.rows[r][c]=i%2==0?'\\':'/';}} return out;''',
        r'''auto z=triangulate_cave_braces(6,3,2); return !(z.valid&&z.anchors==std::vector<std::size_t>{0,2,4,5}&&z.rows==std::vector<std::string>{"+ + ++"," \\ /\\ ","  /  \\"});''',
        r'''auto z=triangulate_cave_braces(4,2,3); if(!z.valid||z.anchors!=std::vector<std::size_t>{0,3}||z.rows[1][3]!='\\') return 1; return triangulate_cave_braces(2,2,1).valid||triangulate_cave_braces(4,1,2).valid||triangulate_cave_braces(4,2,4).valid;''',
        "if(out.anchors.back()!=width-1)", "if(false)", "the terminal roof edge must always receive an anchor",
        ("roof anchor", "alternating brace", "terminal edge", "integer interpolation"),
        ("anchor-generation", "segment-interpolation", "alternating-direction", "edge-completion"),
    ),
)


assert len(CASES) == 20
assert len({case.legacy_id for case in CASES}) == len(CASES)
assert len({case.task_id for case in CASES}) == len(CASES)
assert sum(case.disposition == "repair-in-place" for case in CASES) == 1
