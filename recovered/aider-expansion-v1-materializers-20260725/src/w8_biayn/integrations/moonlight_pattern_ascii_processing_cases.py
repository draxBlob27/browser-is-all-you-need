from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    task_id: str
    title: str
    objective: str
    types: str
    return_type: str
    function: str
    params: str
    contract: str
    body: str
    visible: str
    hidden: str
    negative_old: str
    negative_new: str
    negative_description: str
    profile: tuple[str, ...]


CASES = (
    Case(
        "sierpinski-carpet-stencil",
        "Sierpinski carpet stencil",
        "constructing a base-three recursive removal stencil without precomputed rows",
        "struct CarpetStencil { std::vector<std::string> rows; std::size_t ink_cells = 0; bool valid = false; };",
        "CarpetStencil",
        "cut_sierpinski_carpet",
        "unsigned order, char ink, char void_cell",
        "Orders zero through four are valid. Symbols must be distinct printable non-space bytes. Order zero is one ink cell. For each higher order, a cell is void exactly when some aligned base-three digit of its row and column are both one. Rows are emitted top-to-bottom and never trimmed.",
        r'''if (order > 4 || ink < '!' || ink > '~' || void_cell < '!' || void_cell > '~' || ink == void_cell) return {};
std::size_t side = 1; for (unsigned i = 0; i < order; ++i) side *= 3;
CarpetStencil out; out.valid = true; out.rows.assign(side, std::string(side, ink));
for (std::size_t row = 0; row < side; ++row) for (std::size_t col = 0; col < side; ++col) {
  std::size_t rr = row, cc = col; bool removed = false;
  while (rr != 0 || cc != 0) { if (rr % 3 == 1 && cc % 3 == 1) { removed = true; break; } rr /= 3; cc /= 3; }
  if (removed) out.rows[row][col] = void_cell; else ++out.ink_cells;
}
return out;''',
        r'''auto z = cut_sierpinski_carpet(1, '#', '.'); return !(z.valid && z.rows == std::vector<std::string>{"###", "#.#", "###"} && z.ink_cells == 8);''',
        r'''auto one = cut_sierpinski_carpet(0, 'X', '.'); if (!one.valid || one.rows != std::vector<std::string>{"X"} || one.ink_cells != 1) return 1; auto two = cut_sierpinski_carpet(2, '#', '.'); if (!two.valid || two.rows.size() != 9 || two.rows[4] != "#.#...#.#" || two.ink_cells != 64) return 1; return cut_sierpinski_carpet(5, '#', '.').valid || cut_sierpinski_carpet(1, ' ', '.').valid || cut_sierpinski_carpet(1, '#', '#').valid;''',
        "rr % 3 == 1 && cc % 3 == 1",
        "rr % 3 == 1 || cc % 3 == 1",
        "removing full middle stripes instead of the recursively aligned center blocks",
        ("base-three-recursion", "aligned-hole-predicate", "fixed-square-boundary", "ink-cardinality"),
    ),
    Case(
        "elementary-rule-tape",
        "Elementary rule tape",
        "evolving a finite elementary cellular automaton with dead exterior cells",
        "struct RuleTape { std::vector<std::string> generations; std::size_t live_cells = 0; bool valid = false; };",
        "RuleTape",
        "evolve_elementary_rule",
        "const std::string& seed, unsigned rule, std::size_t generation_count",
        "The seed is nonempty and contains only dot and hash. Rule is in [0,255] and generation_count is in [1,32]. The first emitted row is the seed. Exterior neighbors are dead. Neighborhood bits are left,self,right in weights 4,2,1; rule bit zero is neighborhood 000. Width never changes.",
        r'''if (seed.empty() || rule > 255 || generation_count == 0 || generation_count > 32) return {}; for (char ch : seed) if (ch != '.' && ch != '#') return {};
RuleTape out; out.valid = true; std::string row = seed;
for (std::size_t generation = 0; generation < generation_count; ++generation) {
  out.generations.push_back(row); out.live_cells += static_cast<std::size_t>(std::count(row.begin(), row.end(), '#'));
  std::string next(row.size(), '.'); for (std::size_t col = 0; col < row.size(); ++col) { unsigned index = 0; if (col > 0 && row[col - 1] == '#') index |= 4U; if (row[col] == '#') index |= 2U; if (col + 1 < row.size() && row[col + 1] == '#') index |= 1U; if (((rule >> index) & 1U) != 0U) next[col] = '#'; } row = next;
}
return out;''',
        r'''auto z = evolve_elementary_rule(".#.", 30, 3); return !(z.valid && z.generations == std::vector<std::string>{".#.", "###", "#.."} && z.live_cells == 5);''',
        r'''auto z = evolve_elementary_rule("#", 255, 2); if (!z.valid || z.generations != std::vector<std::string>{"#", "#"} || z.live_cells != 2) return 1; return evolve_elementary_rule("", 30, 2).valid || evolve_elementary_rule(".x", 30, 2).valid || evolve_elementary_rule("#", 256, 2).valid || evolve_elementary_rule("#", 30, 0).valid;''',
        "rule >> index",
        "rule >> (7U - index)",
        "reading Wolfram rule bits in the opposite neighborhood order",
        ("cellular-automaton", "wolfram-bit-index", "dead-exterior", "generation-ledger"),
    ),
    Case(
        "l-system-turtle-plot",
        "L-system turtle plot",
        "rewriting a bounded symbol grammar and interpreting it with stack-aware turtle motion",
        "struct TurtlePlot { std::vector<std::string> rows; std::size_t forward_steps = 0; std::size_t expanded_symbols = 0; bool valid = false; };",
        "TurtlePlot",
        "plot_l_system",
        "const std::string& axiom, const std::map<char, std::string>& productions, unsigned rounds",
        "The axiom is nonempty, rounds is at most four, and every stream including round zero may not exceed 4096 bytes. The axiom and every production replacement may contain only F,+,-,[,] or uppercase A-Z; every production key must be uppercase A-Z, including unused entries. Symbols F,+,-,[,] are commands and other uppercase symbols are inert. Rewriting is simultaneous each round. The turtle starts east at (0,0); plus turns clockwise, minus counter-clockwise, brackets push/pop full pose, and an unmatched bracket is invalid. Every F marks both endpoints. The tight bounding box is returned.",
        r'''auto valid_symbol=[](char symbol){return (symbol>='A'&&symbol<='Z')||symbol=='+'||symbol=='-'||symbol=='['||symbol==']';};auto valid_stream=[&](const std::string& value){return std::all_of(value.begin(),value.end(),valid_symbol);};bool grammar_valid=!axiom.empty()&&rounds<=4&&axiom.size()<=4096&&valid_stream(axiom);for(const auto& production:productions)grammar_valid=grammar_valid&&production.first>='A'&&production.first<='Z'&&valid_stream(production.second);if(!grammar_valid)return {};std::string stream = axiom;
for (unsigned round = 0; round < rounds; ++round) { std::string next; for (char symbol : stream) { auto found = productions.find(symbol); if (found == productions.end()) next.push_back(symbol); else { if(found->second.size()>4096-next.size())return {}; next += found->second; } if (next.size() > 4096) return {}; } stream = next; }
int row = 0, col = 0, direction = 0; const int dr[4] = {0, 1, 0, -1}; const int dc[4] = {1, 0, -1, 0}; std::vector<std::tuple<int,int,int>> stack; std::set<std::pair<int,int>> marks{{0,0}};
TurtlePlot out; for (char command : stream) { if (command == 'F') { row += dr[direction]; col += dc[direction]; marks.insert({row,col}); ++out.forward_steps; } else if (command == '+') direction = (direction + 1) % 4; else if (command == '-') direction = (direction + 3) % 4; else if (command == '[') stack.push_back({row,col,direction}); else if (command == ']') { if (stack.empty()) return {}; std::tie(row,col,direction) = stack.back(); stack.pop_back(); } else if (command < 'A' || command > 'Z') return {}; } if (!stack.empty()) return {};
int min_r = marks.begin()->first, max_r = min_r, min_c = marks.begin()->second, max_c = min_c; for (auto point : marks) { min_r = std::min(min_r, point.first); max_r = std::max(max_r, point.first); min_c = std::min(min_c, point.second); max_c = std::max(max_c, point.second); }
out.rows.assign(static_cast<std::size_t>(max_r-min_r+1), std::string(static_cast<std::size_t>(max_c-min_c+1), '.')); for (auto point : marks) out.rows[static_cast<std::size_t>(point.first-min_r)][static_cast<std::size_t>(point.second-min_c)] = '#'; out.expanded_symbols = stream.size(); out.valid = true; return out;''',
        r'''auto z = plot_l_system("F", {{'F', "F+F"}}, 1);std::string too_large(4097,'F');return !(z.valid && z.rows == std::vector<std::string>{"##", ".#"} && z.forward_steps == 2 && z.expanded_symbols == 3&&!plot_l_system(too_large,{},0).valid&&!plot_l_system("?",{{'?',"F"}},1).valid&&!plot_l_system("F",{{'A',"?"}},0).valid);''',
        r'''std::string boundary(4096,'A');auto zero=plot_l_system(boundary,{},0);if(!zero.valid||zero.expanded_symbols!=4096)return 1;auto z = plot_l_system("F[+F]-F", {}, 0); if (!z.valid || z.forward_steps != 3 || z.rows != std::vector<std::string>{".#", "##", ".#"}) return 1; return plot_l_system("", {}, 0).valid || plot_l_system("F]", {}, 0).valid || plot_l_system("[F", {}, 0).valid || plot_l_system("F?", {}, 0).valid||plot_l_system("F",{{'?',"F"}},0).valid;''',
        "if(!grammar_valid)return {}",
        "if(axiom.empty()||rounds>4)return {}",
        "skipping the round-zero size and complete grammar-alphabet validation",
        ("parallel-string-rewrite", "pose-stack", "tight-bounding-box", "turtle-command-validation"),
    ),
    Case(
        "bayer-threshold-mosaic",
        "Bayer threshold mosaic",
        "applying a fixed ordered-dither threshold matrix to a rectangular intensity image",
        "struct DitherMosaic { std::vector<std::string> rows; std::size_t dark_cells = 0; bool valid = false; };",
        "DitherMosaic",
        "dither_bayer2",
        "const std::vector<std::vector<unsigned>>& intensities, char dark, char light",
        "The image must be nonempty rectangular, every intensity is at most 255, and distinct printable symbols are required. Repeat the 2x2 threshold matrix [[0,128],[192,64]]. A cell is dark when intensity is less than or equal to its threshold. Preserve dimensions and row order.",
        r'''auto printable=[](char symbol){const unsigned char byte=static_cast<unsigned char>(symbol);return byte>=static_cast<unsigned char>('!')&&byte<=static_cast<unsigned char>('~');};const bool symbols_valid=dark!=light&&printable(dark)&&printable(light);if(!symbols_valid)return {};if (intensities.empty() || intensities.front().empty()) return {}; const std::size_t cols = intensities.front().size(); for (const auto& row : intensities) { if (row.size() != cols) return {}; for (unsigned value : row) if (value > 255) return {}; }
const unsigned threshold[2][2] = {{0,128},{192,64}}; DitherMosaic out; out.valid = true;
for (std::size_t r = 0; r < intensities.size(); ++r) { std::string row; for (std::size_t c = 0; c < cols; ++c) { const bool is_dark = intensities[r][c] <= threshold[r%2][c%2]; row.push_back(is_dark ? dark : light); out.dark_cells += is_dark; } out.rows.push_back(row); } return out;''',
        r'''auto z = dither_bayer2({{0,255},{128,64}}, '#', '.'); return !(z.valid && z.rows == std::vector<std::string>{"#.", "##"} && z.dark_cells == 3&&!dither_bayer2({{0}},static_cast<char>(127),'.').valid);''',
        r'''auto z = dither_bayer2({{1,128}}, 'X', '_'); if (!z.valid || z.rows != std::vector<std::string>{"_X"} || z.dark_cells != 1) return 1; return dither_bayer2({}, '#', '.').valid || dither_bayer2({{}}, '#', '.').valid || dither_bayer2({{1},{2,3}}, '#', '.').valid || dither_bayer2({{256}}, '#', '.').valid || dither_bayer2({{0}}, '#', '#').valid||dither_bayer2({{0}},static_cast<char>(255),'.').valid;''',
        "if(!symbols_valid)return {}",
        "if(!symbols_valid&&dark==light)return {}",
        "accepting DEL and high-bit bytes as output symbols",
        ("ordered-dither", "periodic-threshold-matrix", "rectangular-validation", "dark-cell-count"),
    ),
    Case(
        "bresenham-segment-raster",
        "Bresenham segment raster",
        "rasterizing an inclusive integer segment with the signed error recurrence",
        "struct GridPoint { int x = 0; int y = 0; }; struct SegmentRaster { std::vector<std::string> rows; GridPoint origin; std::size_t plotted = 0; bool valid = false; };",
        "SegmentRaster",
        "raster_segment",
        "GridPoint from, GridPoint to, char ink",
        "Coordinates must lie in [-64,64] and ink must be printable non-space. Use the inclusive Bresenham recurrence for every octant. Return the tight axis-aligned bounding box with origin equal to its minimum x,y. Both endpoints are always plotted; coincident endpoints plot once.",
        r'''if (ink < '!' || ink > '~' || from.x < -64 || from.x > 64 || from.y < -64 || from.y > 64 || to.x < -64 || to.x > 64 || to.y < -64 || to.y > 64) return {};
const int min_x = std::min(from.x,to.x), max_x = std::max(from.x,to.x), min_y = std::min(from.y,to.y), max_y = std::max(from.y,to.y); SegmentRaster out; out.valid = true; out.origin = {min_x,min_y}; out.rows.assign(static_cast<std::size_t>(max_y-min_y+1), std::string(static_cast<std::size_t>(max_x-min_x+1), '.'));
int x = from.x, y = from.y; const int dx = std::abs(to.x-from.x), sx = from.x < to.x ? 1 : -1, dy = -std::abs(to.y-from.y), sy = from.y < to.y ? 1 : -1; int error = dx + dy;
for (;;) { out.rows[static_cast<std::size_t>(y-min_y)][static_cast<std::size_t>(x-min_x)] = ink; ++out.plotted; if (x == to.x && y == to.y) break; const int twice = 2*error; if (twice >= dy) { error += dy; x += sx; } if (twice <= dx) { error += dx; y += sy; } }
return out;''',
        r'''auto z = raster_segment({0,0},{2,1},'#'); return !(z.valid && z.rows == std::vector<std::string>{"#..", ".##"} && z.plotted == 3 && z.origin.x == 0 && z.origin.y == 0);''',
        r'''auto z = raster_segment({2,2},{2,2},'X'); if (!z.valid || z.rows != std::vector<std::string>{"X"} || z.plotted != 1 || z.origin.x != 2 || z.origin.y != 2) return 1; auto reverse = raster_segment({2,1},{0,0},'#'); if (!reverse.valid || reverse.plotted != 3) return 1; return raster_segment({-65,0},{0,0},'#').valid || raster_segment({0,0},{0,0},' ').valid;''',
        "if (twice <= dx)",
        "if (twice < dx)",
        "dropping the vertical step when the signed error is exactly on its boundary",
        ("signed-error-recurrence", "all-octant-step", "inclusive-endpoints", "tight-coordinate-origin"),
    ),
    Case(
        "midpoint-ellipse-raster",
        "Midpoint ellipse raster",
        "drawing four-way symmetric ellipse boundary pixels with midpoint region transitions",
        "struct EllipseRaster { std::vector<std::string> rows; std::size_t boundary_cells = 0; bool valid = false; };",
        "EllipseRaster",
        "raster_midpoint_ellipse",
        "unsigned radius_x, unsigned radius_y, char ink",
        "Radii are in [1,24] and ink is printable non-space. Use the midpoint ellipse algorithm, first stepping while the x-gradient is smaller than the y-gradient and then finishing the second region. Plot all four symmetric points into a (2*radius_y+1) by (2*radius_x+1) canvas and count unique boundary cells.",
        r'''if (radius_x == 0 || radius_y == 0 || radius_x > 24 || radius_y > 24 || ink < '!' || ink > '~') return {}; EllipseRaster out; out.valid = true; out.rows.assign(2*radius_y+1, std::string(2*radius_x+1,'.'));std::set<std::pair<long,long>> visited;
auto plot = [&](long x,long y){ const long cx=static_cast<long>(radius_x), cy=static_cast<long>(radius_y); const std::pair<long,long> points[4]={ {cy+y,cx+x},{cy+y,cx-x},{cy-y,cx+x},{cy-y,cx-x} }; for(auto point:points){char& cell=out.rows[static_cast<std::size_t>(point.first)][static_cast<std::size_t>(point.second)]; if(visited.insert(point).second){cell=ink;++out.boundary_cells;}}};
const double rx2=static_cast<double>(radius_x)*radius_x, ry2=static_cast<double>(radius_y)*radius_y; long x=0,y=static_cast<long>(radius_y); double dx=0.0,dy=2.0*rx2*static_cast<double>(y); double p=ry2-rx2*static_cast<double>(radius_y)+0.25*rx2;
while(dx<dy){plot(x,y);++x;dx+=2.0*ry2;if(p<0.0)p+=ry2+dx;else{--y;dy-=2.0*rx2;p+=ry2+dx-dy;}}
p=ry2*(static_cast<double>(x)+0.5)*(static_cast<double>(x)+0.5)+rx2*(static_cast<double>(y)-1.0)*(static_cast<double>(y)-1.0)-rx2*ry2;
while(y>=0){plot(x,y);--y;dy-=2.0*rx2;if(p>0.0)p+=rx2-dy;else{++x;dx+=2.0*ry2;p+=rx2-dy+dx;}}
return out;''',
        r'''auto z = raster_midpoint_ellipse(2,1,'#');auto dot=raster_midpoint_ellipse(1,1,'.');return !(z.valid && z.rows == std::vector<std::string>{".###.", "#...#", ".###."} && z.boundary_cells == 8&&dot.valid&&dot.rows==std::vector<std::string>{"...","...","..."}&&dot.boundary_cells==4);''',
        r'''auto z = raster_midpoint_ellipse(1,1,'X'); if (!z.valid || z.rows.size()!=3 || z.rows[0][1]!='X' || z.rows[1][0]!='X' || z.rows[1][2]!='X' || z.rows[2][1]!='X') return 1; return raster_midpoint_ellipse(0,1,'#').valid || raster_midpoint_ellipse(25,1,'#').valid || raster_midpoint_ellipse(1,1,' ').valid;''',
        "if(visited.insert(point).second)",
        "if(cell=='.')",
        "using the rendered dot byte as the unique-visit sentinel",
        ("midpoint-conic", "two-region-transition", "four-way-symmetry", "unique-boundary-count"),
    ),
    Case(
        "scanline-polygon-raster",
        "Scanline polygon raster",
        "filling a simple integer polygon by sorted scanline intersections at cell centers",
        "struct Vertex { int x = 0; int y = 0; }; struct PolygonRaster { std::vector<std::string> rows; Vertex origin; std::size_t filled = 0; bool valid = false; };",
        "PolygonRaster",
        "fill_polygon_scanlines",
        "const std::vector<Vertex>& vertices, char ink",
        "At least three vertices with coordinates in [-32,32] are required; consecutive or nonadjacent duplicate vertices, a repeated closing vertex, self-crossings, self-touches, and collinear edge overlap are invalid. Adjacent edges may meet only at their shared endpoint; collinear continuation without reversal is allowed. Treat edges as a closed simple polygon. For every half-integer scanline, sort non-horizontal edge intersections and fill cell centers by the even-odd rule, pairing intersections from left to right. The output covers [min_x,max_x) and [min_y,max_y).",
        r'''if(vertices.size()<3||ink<'!'||ink>'~') return {}; for(std::size_t i=0;i<vertices.size();++i){const auto& a=vertices[i];const auto& b=vertices[(i+1)%vertices.size()];if(a.x<-32||a.x>32||a.y<-32||a.y>32||(a.x==b.x&&a.y==b.y))return {};}auto cross=[](Vertex a,Vertex b,Vertex c){return static_cast<long long>(b.x-a.x)*(c.y-a.y)-static_cast<long long>(b.y-a.y)*(c.x-a.x);};auto on_segment=[&](Vertex a,Vertex b,Vertex p){return cross(a,b,p)==0&&p.x>=std::min(a.x,b.x)&&p.x<=std::max(a.x,b.x)&&p.y>=std::min(a.y,b.y)&&p.y<=std::max(a.y,b.y);};auto intersects=[&](Vertex a,Vertex b,Vertex c,Vertex d){const long long ab_c=cross(a,b,c),ab_d=cross(a,b,d),cd_a=cross(c,d,a),cd_b=cross(c,d,b);if(((ab_c>0&&ab_d<0)||(ab_c<0&&ab_d>0))&&((cd_a>0&&cd_b<0)||(cd_a<0&&cd_b>0)))return true;return on_segment(a,b,c)||on_segment(a,b,d)||on_segment(c,d,a)||on_segment(c,d,b);};for(std::size_t i=0;i<vertices.size();++i){const Vertex previous=vertices[(i+vertices.size()-1)%vertices.size()],current=vertices[i],next=vertices[(i+1)%vertices.size()];if(cross(previous,current,next)==0){const long long first_x=current.x-previous.x,first_y=current.y-previous.y,second_x=next.x-current.x,second_y=next.y-current.y;if(first_x*second_x+first_y*second_y<0)return {};}}for(std::size_t i=0;i<vertices.size();++i)for(std::size_t j=i+1;j<vertices.size();++j){if(j==i+1||(i==0&&j+1==vertices.size()))continue;const Vertex a=vertices[i],b=vertices[(i+1)%vertices.size()],c=vertices[j],d=vertices[(j+1)%vertices.size()];if(intersects(a,b,c,d))return {};} int min_x=vertices[0].x,max_x=min_x,min_y=vertices[0].y,max_y=min_y;for(auto v:vertices){min_x=std::min(min_x,v.x);max_x=std::max(max_x,v.x);min_y=std::min(min_y,v.y);max_y=std::max(max_y,v.y);}if(min_x==max_x||min_y==max_y)return {};
PolygonRaster out;out.valid=true;out.origin={min_x,min_y};out.rows.assign(static_cast<std::size_t>(max_y-min_y),std::string(static_cast<std::size_t>(max_x-min_x),'.'));
for(int y=min_y;y<max_y;++y){const double scan=static_cast<double>(y)+0.5;std::vector<double> crossings;for(std::size_t i=0;i<vertices.size();++i){const auto a=vertices[i],b=vertices[(i+1)%vertices.size()];if((static_cast<double>(a.y)<=scan&&scan<static_cast<double>(b.y))||(static_cast<double>(b.y)<=scan&&scan<static_cast<double>(a.y))){crossings.push_back(static_cast<double>(a.x)+(scan-a.y)*static_cast<double>(b.x-a.x)/static_cast<double>(b.y-a.y));}}std::sort(crossings.begin(),crossings.end());if(crossings.size()%2!=0)return {};for(std::size_t pair=0;pair<crossings.size();pair+=2)for(int x=min_x;x<max_x;++x){const double center=static_cast<double>(x)+0.5;if(center>=crossings[pair]&&center<crossings[pair+1]){out.rows[static_cast<std::size_t>(y-min_y)][static_cast<std::size_t>(x-min_x)]=ink;++out.filled;}}}
return out;''',
        r'''auto z=fill_polygon_scanlines({{0,0},{3,0},{0,3}},'#');return !(z.valid&&z.rows==std::vector<std::string>{"##.","#..","..."}&&z.filled==3&&z.origin.x==0&&z.origin.y==0&&!fill_polygon_scanlines({{0,0},{2,2},{0,2},{2,0}},'#').valid);''',
        r'''auto z=fill_polygon_scanlines({{0,0},{2,0},{2,2},{0,2}},'X');if(!z.valid||z.rows!=std::vector<std::string>{"XX","XX"}||z.filled!=4)return 1;return fill_polygon_scanlines({{0,0},{1,1}},'#').valid||fill_polygon_scanlines({{0,0},{1,0},{1,0}},'#').valid||fill_polygon_scanlines({{0,0},{0,1},{0,2}},'#').valid||fill_polygon_scanlines({{0,0},{3,0},{1,0},{1,2},{0,2}},'#').valid||fill_polygon_scanlines({{0,0},{3,0},{3,2},{0,2},{2,0}},'#').valid;''',
        "if(intersects(a,b,c,d))return {}",
        "if(intersects(a,b,c,d)&&false)return {}",
        "accepting self-crossing or overlapping nonadjacent polygon edges",
        ("even-odd-scanline", "sorted-intersections", "half-open-cell-centers", "polygon-bounds"),
    ),
    Case(
        "cubic-bezier-raster",
        "Cubic Bezier raster",
        "sampling a cubic Bezier curve and deduplicating rounded lattice points in parameter order",
        "struct ControlPoint { double x = 0.0; double y = 0.0; }; struct BezierRaster { std::vector<std::string> rows; std::vector<std::pair<int,int>> samples; bool valid = false; };",
        "BezierRaster",
        "raster_cubic_bezier",
        "ControlPoint p0, ControlPoint p1, ControlPoint p2, ControlPoint p3, std::size_t sample_count",
        "sample_count is in [2,129], all coordinates are finite and in [-32,32]. Sample t=i/(sample_count-1), including both endpoints. Evaluate all four Bernstein terms, round with lround, retain first occurrence of each lattice point in parameter order, and return their tight hash-marked canvas.",
        r'''const ControlPoint points[4]={p0,p1,p2,p3};if(sample_count<2||sample_count>129)return {};for(auto p:points)if(!std::isfinite(p.x)||!std::isfinite(p.y)||p.x<-32||p.x>32||p.y<-32||p.y>32)return {};BezierRaster out;std::set<std::pair<int,int>> seen;
for(std::size_t i=0;i<sample_count;++i){const double t=static_cast<double>(i)/static_cast<double>(sample_count-1),u=1.0-t;const double x=u*u*u*p0.x+3*u*u*t*p1.x+3*u*t*t*p2.x+t*t*t*p3.x;const double y=u*u*u*p0.y+3*u*u*t*p1.y+3*u*t*t*p2.y+t*t*t*p3.y;std::pair<int,int> point{static_cast<int>(std::lround(x)),static_cast<int>(std::lround(y))};if(seen.insert(point).second)out.samples.push_back(point);}int min_x=out.samples[0].first,max_x=min_x,min_y=out.samples[0].second,max_y=min_y;for(auto point:out.samples){min_x=std::min(min_x,point.first);max_x=std::max(max_x,point.first);min_y=std::min(min_y,point.second);max_y=std::max(max_y,point.second);}out.rows.assign(static_cast<std::size_t>(max_y-min_y+1),std::string(static_cast<std::size_t>(max_x-min_x+1),'.'));for(auto point:out.samples)out.rows[static_cast<std::size_t>(point.second-min_y)][static_cast<std::size_t>(point.first-min_x)]='#';out.valid=true;return out;''',
        r'''auto z=raster_cubic_bezier({0,0},{3,0},{3,3},{0,3},5);return !(z.valid&&z.rows==std::vector<std::string>{"#.#","...","..#","#.#"}&&z.samples==std::vector<std::pair<int,int>>{{0,0},{2,0},{2,2},{2,3},{0,3}});''',
        r'''auto z=raster_cubic_bezier({0,0},{0,3},{3,3},{3,0},5);if(!z.valid||z.samples.front()!=std::pair<int,int>{0,0}||z.samples.back()!=std::pair<int,int>{3,0}||z.rows.size()<2)return 1;return raster_cubic_bezier({0,0},{1,1},{2,2},{3,3},1).valid||raster_cubic_bezier({33,0},{1,1},{2,2},{3,3},4).valid;''',
        "3*u*u*t*p1.x",
        "u*u*t*p1.x",
        "dropping the first control point's Bernstein coefficient",
        ("bernstein-polynomial", "parameter-order-dedup", "rounded-lattice", "sample-inclusive-endpoints"),
    ),
    Case(
        "signed-histogram-baseline",
        "Signed histogram baseline",
        "rendering signed bars around an explicit zero axis with stable column labels",
        "struct HistogramPlot { std::vector<std::string> rows; std::size_t positive_cells = 0; std::size_t negative_cells = 0; bool valid = false; };",
        "HistogramPlot",
        "plot_signed_histogram",
        "const std::vector<int>& values, unsigned half_height",
        "values is nonempty, half_height is in [1,20], and every absolute value is at most half_height. Emit 2*half_height+1 rows. Positive cells grow upward with caret, negative cells downward with v, zero cells use 0 on the hyphen baseline, and nonzero columns use plus on the baseline. Preserve input column order.",
        r'''if(values.empty()||half_height==0||half_height>20)return {};for(int value:values)if(value>static_cast<int>(half_height)||value< -static_cast<int>(half_height))return {};HistogramPlot out;out.valid=true;out.rows.assign(2*half_height+1,std::string(values.size(),' '));const std::size_t axis=half_height;
for(std::size_t c=0;c<values.size();++c){const int value=values[c];out.rows[axis][c]=value==0?'0':'+';if(value>0)for(int level=1;level<=value;++level){out.rows[axis-static_cast<std::size_t>(level)][c]='^';++out.positive_cells;}if(value<0)for(int level=1;level<=-value;++level){out.rows[axis+static_cast<std::size_t>(level)][c]='v';++out.negative_cells;}}
return out;''',
        r'''auto z=plot_signed_histogram({2,0,-1},2);return !(z.valid&&z.rows==std::vector<std::string>{"^  ","^  ","+0+","  v","   "}&&z.positive_cells==2&&z.negative_cells==1);''',
        r'''auto z=plot_signed_histogram({-2,1},2);if(!z.valid||z.rows[0]!="  "||z.rows[1]!=" ^"||z.rows[3][0]!='v'||z.rows[4][0]!='v')return 1;return plot_signed_histogram({},2).valid||plot_signed_histogram({1},0).valid||plot_signed_histogram({3},2).valid;''',
        "value==0?'0':'+'",
        "value==0?'+':'+'",
        "losing the distinct documented zero-column baseline marker",
        ("signed-axis-layout", "opposed-bar-growth", "zero-marker", "positive-negative-ledgers"),
    ),
    Case(
        "crossword-start-numbering",
        "Crossword start numbering",
        "numbering across and down entry starts in row-major order on a blocked ASCII grid",
        "struct CrosswordNumbers { std::vector<std::vector<unsigned>> numbers; std::vector<std::string> display; unsigned next_number = 1; bool valid = false; };",
        "CrosswordNumbers",
        "number_crossword_starts",
        "const std::vector<std::string>& grid",
        "The grid must be nonempty rectangular and contain only dot open cells and hash blocks. An across start is open, has a blocked/outside left neighbor, and has an open right neighbor. A down start is analogous above/below. A qualifying cell receives one number even if both starts apply. Number row-major from one. Display blocks as ##, unnumbered open cells as two dots, and numbered cells as zero-padded two digits; reject more than 99 starts.",
        r'''if(grid.empty()||grid.front().empty())return {};const std::size_t cols=grid.front().size();for(const auto& row:grid){if(row.size()!=cols)return {};for(char ch:row)if(ch!='.'&&ch!='#')return {};}CrosswordNumbers out;out.valid=true;out.numbers.assign(grid.size(),std::vector<unsigned>(cols,0));unsigned number=1;
for(std::size_t r=0;r<grid.size();++r)for(std::size_t c=0;c<cols;++c)if(grid[r][c]=='.'){const bool across=(c==0||grid[r][c-1]=='#')&&c+1<cols&&grid[r][c+1]=='.';const bool down=(r==0||grid[r-1][c]=='#')&&r+1<grid.size()&&grid[r+1][c]=='.';if(across||down){if(number>99)return {};out.numbers[r][c]=number++;}}
for(std::size_t r=0;r<grid.size();++r){std::string line;for(std::size_t c=0;c<cols;++c){if(grid[r][c]=='#')line+="##";else if(out.numbers[r][c]==0)line+="..";else{line.push_back(static_cast<char>('0'+out.numbers[r][c]/10));line.push_back(static_cast<char>('0'+out.numbers[r][c]%10));}}out.display.push_back(line);}out.next_number=number;return out;''',
        r'''auto z=number_crossword_starts({"..#","...","#.."});return !(z.valid&&z.numbers==std::vector<std::vector<unsigned>>{{1,2,0},{3,0,4},{0,5,0}}&&z.display[0]=="0102##"&&z.next_number==6);''',
        r'''auto z=number_crossword_starts({"."});if(!z.valid||z.numbers[0][0]!=0||z.display!=std::vector<std::string>{".."}||z.next_number!=1)return 1;return number_crossword_starts({}).valid||number_crossword_starts({".",".."}).valid||number_crossword_starts({"A"}).valid;''',
        "if(across||down)",
        "if(across&&down)",
        "numbering only cells that begin both orientations",
        ("entry-start-predicates", "row-major-numbering", "dual-orientation-coalescing", "two-column-display"),
    ),
    Case(
        "nonogram-clue-gutters",
        "Nonogram clue gutters",
        "extracting maximal filled runs and aligning row and column clues at their solving edges",
        "struct NonogramGutters { std::vector<std::string> row_clues; std::vector<std::string> column_clues; std::size_t max_row_runs = 0; std::size_t max_column_runs = 0; bool valid = false; };",
        "NonogramGutters",
        "build_nonogram_gutters",
        "const std::vector<std::string>& pixels",
        "The bitmap is nonempty rectangular and contains only dot and hash. Convert each row and column to comma-separated positive maximal hash-run lengths; an empty line has clue 0. Preserve top-to-bottom row order and left-to-right column order. Report the maximum number of runs on either axis, counting an empty clue as zero runs.",
        r'''if(pixels.empty()||pixels.front().empty())return {};const std::size_t cols=pixels.front().size();for(const auto& row:pixels){if(row.size()!=cols)return {};for(char ch:row)if(ch!='.'&&ch!='#')return {};}NonogramGutters out;out.valid=true;
auto clue=[](const std::string& line,std::size_t& run_count){std::string result;std::size_t run=0;for(std::size_t i=0;i<=line.size();++i){if(i<line.size()&&line[i]=='#'){++run;}else if(run!=0){if(!result.empty())result.push_back(',');result+=std::to_string(run);++run_count;run=0;}}if(result.empty())result="0";return result;};
for(const auto& row:pixels){std::size_t count=0;out.row_clues.push_back(clue(row,count));out.max_row_runs=std::max(out.max_row_runs,count);}for(std::size_t c=0;c<cols;++c){std::string column;for(const auto& row:pixels)column.push_back(row[c]);std::size_t count=0;out.column_clues.push_back(clue(column,count));out.max_column_runs=std::max(out.max_column_runs,count);}return out;''',
        r'''auto z=build_nonogram_gutters({"#.#","###"});return !(z.valid&&z.row_clues==std::vector<std::string>{"1,1","3"}&&z.column_clues==std::vector<std::string>{"2","1","2"}&&z.max_row_runs==2&&z.max_column_runs==1);''',
        r'''auto z=build_nonogram_gutters({"...",".#."});if(!z.valid||z.row_clues!=std::vector<std::string>{"0","1"}||z.column_clues!=std::vector<std::string>{"0","1","0"})return 1;return build_nonogram_gutters({}).valid||build_nonogram_gutters({"#","##"}).valid||build_nonogram_gutters({"x"}).valid;''',
        "i<=line.size()",
        "i<line.size()",
        "failing to flush a maximal run that reaches the far edge",
        ("maximal-run-extraction", "axis-transposition", "ordered-clue-serialization", "empty-line-zero"),
    ),
    Case(
        "terminal-overstrike-buffer",
        "Terminal overstrike buffer",
        "executing printable bytes, backspace, carriage return, and line feed against a bounded page",
        "struct PrinterPage { std::vector<std::string> rows; std::size_t cursor_row = 0; std::size_t cursor_col = 0; std::size_t overwritten = 0; bool valid = false; };",
        "PrinterPage",
        "print_overstrike_stream",
        "std::size_t rows, std::size_t cols, const std::string& stream",
        "Dimensions are in [1,32]. Printable ASCII writes at the cursor and advances one column without wrapping. Backspace moves left and is invalid at column zero. Carriage return sets column zero. Line feed advances one row without changing column. Any move or write outside the page, any unsupported control, or an empty stream is invalid with no partial result. Count a write over a non-space cell as overwritten even when the byte is unchanged.",
        r'''if(rows==0||cols==0||rows>32||cols>32||stream.empty())return {};PrinterPage out;out.rows.assign(rows,std::string(cols,' '));
for(unsigned char byte:stream){if(byte=='\b'){if(out.cursor_col==0)return {};--out.cursor_col;}else if(byte=='\r'){out.cursor_col=0;}else if(byte=='\n'){if(out.cursor_row+1>=rows)return {};++out.cursor_row;}else if(byte>=32&&byte<=126){if(out.cursor_col>=cols)return {};char& cell=out.rows[out.cursor_row][out.cursor_col];if(cell!=' ')++out.overwritten;cell=static_cast<char>(byte);++out.cursor_col;}else return {};}
out.valid=true;return out;''',
        r'''auto z=print_overstrike_stream(1,4,"AB\bC");return !(z.valid&&z.rows==std::vector<std::string>{"AC  "}&&z.cursor_col==2&&z.overwritten==1);''',
        r'''auto z=print_overstrike_stream(2,3,"AB\rX\nZ");if(!z.valid||z.rows!=std::vector<std::string>{"XB "," Z "}||z.cursor_row!=1||z.cursor_col!=2||z.overwritten!=1)return 1;return print_overstrike_stream(0,3,"A").valid||print_overstrike_stream(1,1,"AB").valid||print_overstrike_stream(1,2,"\b").valid||print_overstrike_stream(1,2,"").valid;''',
        "--out.cursor_col",
        "out.cursor_col=0",
        "treating backspace as carriage return rather than one-cell cursor motion",
        ("bounded-cursor-state", "destructive-overstrike", "distinct-control-bytes", "atomic-invalid-stream"),
    ),
    Case(
        "ansi-visible-column-map",
        "ANSI visible column map",
        "removing valid SGR escape sequences while mapping visible cells back to source offsets",
        "struct VisibleColumns { std::string text; std::vector<std::size_t> source_offsets; std::vector<std::size_t> columns; bool valid = false; };",
        "VisibleColumns",
        "map_ansi_visible_columns",
        "const std::string& bytes, std::size_t tab_stop",
        "bytes is nonempty and tab_stop is in [1,16]. Accept printable ASCII, tab, and CSI SGR sequences ESC [ parameters m where parameters are digits and semicolons (empty is allowed). SGR bytes occupy no columns. A tab emits spaces up to the next strict tab-stop boundary, each mapped to the tab byte. Reject all other controls, incomplete escapes, and parameter values above 255. Record zero-based output columns and original source byte offsets.",
        r'''if(bytes.empty()||tab_stop==0||tab_stop>16)return {};VisibleColumns out;
for(std::size_t i=0;i<bytes.size();){const unsigned char ch=static_cast<unsigned char>(bytes[i]);if(ch==27){if(i+2>=bytes.size()||bytes[i+1]!='[')return {};std::size_t j=i+2;unsigned value=0;bool have=false;for(;j<bytes.size()&&bytes[j]!='m';++j){if(bytes[j]==';'){if(have&&value>255)return {};value=0;have=false;}else if(bytes[j]>='0'&&bytes[j]<='9'){have=true;value=value*10U+static_cast<unsigned>(bytes[j]-'0');if(value>255)return {};}else return {};}if(j==bytes.size())return {};i=j+1;continue;}if(ch=='\t'){const std::size_t padding=tab_stop-(out.text.size()%tab_stop);for(std::size_t k=0;k<padding;++k){out.columns.push_back(out.text.size());out.source_offsets.push_back(i);out.text.push_back(' ');}++i;continue;}if(ch<32||ch>126)return {};out.columns.push_back(out.text.size());out.source_offsets.push_back(i);out.text.push_back(static_cast<char>(ch));++i;}
out.valid=true;return out;''',
        r'''auto z=map_ansi_visible_columns(std::string("A\x1b[31mB\x1b[0m\tC"),4);return !(z.valid&&z.text=="AB  C"&&z.columns==std::vector<std::size_t>{0,1,2,3,4}&&z.source_offsets.front()==0&&z.source_offsets.back()==12);''',
        r'''auto z=map_ansi_visible_columns("AB\tC",2);if(!z.valid||z.text!="AB  C"||z.source_offsets[2]!=2)return 1;return map_ansi_visible_columns("",4).valid||map_ansi_visible_columns("A\x1b[31",4).valid||map_ansi_visible_columns("A\n",4).valid||map_ansi_visible_columns("A",0).valid;''',
        "tab_stop-(out.text.size()%tab_stop)",
        "tab_stop",
        "always inserting a full tab stop instead of advancing to the next boundary",
        ("csi-sgr-state-machine", "zero-width-escape", "tab-boundary-expansion", "source-offset-ledger"),
    ),
    Case(
        "box-drawing-junction-map",
        "Box-drawing junction map",
        "validating reciprocal cardinal links and synthesizing an ASCII junction glyph for every cell",
        "struct JunctionMap { std::vector<std::string> rows; std::size_t endpoints = 0; std::size_t junctions = 0; bool valid = false; };",
        "JunctionMap",
        "render_junction_map",
        "const std::vector<std::vector<unsigned>>& masks",
        "The nonempty rectangular mask grid uses bits north=1,east=2,south=4,west=8 and no other bits. Every link must remain in bounds and be reciprocated by its neighbor. Zero renders dot; north/south-only renders vertical bar; east/west-only renders hyphen; every turn or degree at least three renders plus. Count degree-one endpoints and degree-three/four junctions in row-major order.",
        r'''if(masks.empty()||masks.front().empty())return {};const std::size_t cols=masks.front().size();for(const auto& row:masks)if(row.size()!=cols)return {};const int dr[4]={-1,0,1,0},dc[4]={0,1,0,-1};const unsigned bit[4]={1,2,4,8},opposite[4]={4,8,1,2};JunctionMap out;out.valid=true;
for(std::size_t r=0;r<masks.size();++r){std::string line;for(std::size_t c=0;c<cols;++c){const unsigned mask=masks[r][c];if((mask&~15U)!=0U)return {};for(int d=0;d<4;++d)if((mask&bit[d])!=0U){const int nr=static_cast<int>(r)+dr[d],nc=static_cast<int>(c)+dc[d];if(nr<0||nc<0||nr>=static_cast<int>(masks.size())||nc>=static_cast<int>(cols)||(masks[static_cast<std::size_t>(nr)][static_cast<std::size_t>(nc)]&opposite[d])==0U)return {};}const unsigned degree=static_cast<unsigned>(((mask&1U)!=0U)+((mask&2U)!=0U)+((mask&4U)!=0U)+((mask&8U)!=0U));out.endpoints+=degree==1;out.junctions+=degree>=3;if(mask==0)line.push_back('.');else if((mask&~5U)==0U)line.push_back('|');else if((mask&~10U)==0U)line.push_back('-');else line.push_back('+');}out.rows.push_back(line);}return out;''',
        r'''auto z=render_junction_map({{6,12},{3,9}});return !(z.valid&&z.rows==std::vector<std::string>{"++","++"}&&z.endpoints==0&&z.junctions==0);''',
        r'''auto z=render_junction_map({{2,8}});if(!z.valid||z.rows!=std::vector<std::string>{"--"}||z.endpoints!=2||z.junctions!=0)return 1;return render_junction_map({}).valid||render_junction_map({{2}}).valid||render_junction_map({{16}}).valid||render_junction_map({{2,0}}).valid;''',
        "else line.push_back('+')",
        "else line.push_back('-')",
        "flattening turns and multi-way junctions into horizontal strokes",
        ("reciprocal-link-validation", "cardinal-bitmask", "degree-glyph-synthesis", "endpoint-junction-ledgers"),
    ),
    Case(
        "vertical-seam-carve",
        "Vertical seam carve",
        "removing a minimum-energy top-to-bottom seam with deterministic predecessor ties",
        "struct SeamCarve { std::vector<std::string> rows; std::vector<std::size_t> seam_columns; unsigned total_energy = 0; bool valid = false; };",
        "SeamCarve",
        "carve_vertical_seam",
        "const std::vector<std::string>& pixels, const std::vector<std::vector<unsigned>>& energy",
        "pixels and energy must be matching nonempty rectangles with width at least two; pixel bytes are printable and energy values are at most 100000. A seam selects one column per row and adjacent columns differ by at most one. Minimize total energy by dynamic programming. On equal predecessor costs choose the smaller predecessor column; among final minima choose the smaller column. If the minimum seam total exceeds UINT_MAX the complete input is invalid. Remove exactly those cells and preserve every remaining byte, including spaces.",
        r'''if(pixels.empty()||pixels.front().size()<2||energy.size()!=pixels.size())return {};const std::size_t rows=pixels.size(),cols=pixels.front().size();for(std::size_t r=0;r<rows;++r){if(pixels[r].size()!=cols||energy[r].size()!=cols)return {};for(unsigned char ch:pixels[r])if(ch<32||ch>126)return {};for(unsigned value:energy[r])if(value>100000)return {};}std::vector<std::vector<unsigned long long>> cost(rows,std::vector<unsigned long long>(cols));std::vector<std::vector<std::size_t>> parent(rows,std::vector<std::size_t>(cols));for(std::size_t c=0;c<cols;++c)cost[0][c]=energy[0][c];
for(std::size_t r=1;r<rows;++r)for(std::size_t c=0;c<cols;++c){std::size_t best=c;for(std::size_t p=(c==0?0:c-1);p<=std::min(cols-1,c+1);++p)if(cost[r-1][p]<cost[r-1][best]||(cost[r-1][p]==cost[r-1][best]&&p<best))best=p;parent[r][c]=best;cost[r][c]=cost[r-1][best]+energy[r][c];}
std::size_t end=0;for(std::size_t c=1;c<cols;++c)if(cost.back()[c]<cost.back()[end])end=c;if(cost.back()[end]>std::numeric_limits<unsigned>::max())return {};SeamCarve out;out.valid=true;out.total_energy=static_cast<unsigned>(cost.back()[end]);out.seam_columns.assign(rows,0);for(std::size_t r=rows;r-- >0;){out.seam_columns[r]=end;if(r!=0)end=parent[r][end];}for(std::size_t r=0;r<rows;++r){std::string row=pixels[r];row.erase(row.begin()+static_cast<std::ptrdiff_t>(out.seam_columns[r]));out.rows.push_back(row);}return out;''',
        r'''auto z=carve_vertical_seam({"ab","cd"},{{1,1},{1,1}});std::vector<std::string> huge_pixels(42950,"ab");std::vector<std::vector<unsigned>> huge_energy(42950,std::vector<unsigned>{100000,100000});return !(z.valid&&z.seam_columns==std::vector<std::size_t>{0,0}&&z.rows==std::vector<std::string>{"b","d"}&&z.total_energy==2&&!carve_vertical_seam(huge_pixels,huge_energy).valid);''',
        r'''auto z=carve_vertical_seam({"abc","def","ghi"},{{1,9,9},{9,1,9},{9,1,9}});if(!z.valid||z.seam_columns!=std::vector<std::size_t>{0,1,1}||z.rows!=std::vector<std::string>{"bc","df","gi"}||z.total_energy!=3)return 1;std::vector<std::string> below_pixels(42949,"ab");std::vector<std::vector<unsigned>> below_energy(42949,std::vector<unsigned>{100000,100000});auto below=carve_vertical_seam(below_pixels,below_energy);if(!below.valid||below.total_energy!=4294900000U)return 1;return carve_vertical_seam({},{}).valid||carve_vertical_seam({"a"},{{1}}).valid||carve_vertical_seam({"ab"},{{1}}).valid;''',
        "if(cost.back()[end]>std::numeric_limits<unsigned>::max())return {}",
        "if(false)return {}",
        "narrowing an overflowing minimum seam total into unsigned",
        ("dynamic-programming-seam", "adjacent-predecessors", "leftmost-tie", "byte-preserving-removal"),
    ),
    Case(
        "morse-timing-banner",
        "Morse timing banner",
        "encoding letters into exact mark and gap units and rendering a two-level timing strip",
        "struct MorseBanner { std::vector<std::string> rows; std::size_t mark_units = 0; std::size_t total_units = 0; bool valid = false; };",
        "MorseBanner",
        "render_morse_banner",
        "const std::string& message",
        "message is nonempty uppercase A-Z words separated by single spaces; leading, trailing, or repeated spaces are invalid. Use the international A-Z Morse table. A dot is one mark unit, dash three, intra-symbol gaps one, letter gaps three, and word gaps seven. Render high units as hash in row zero and low units as underscore in row one, with spaces in the opposite row. No gap follows the final letter.",
        r'''static const std::map<char,std::string> code={{'A',".-"},{'B',"-..."},{'C',"-.-."},{'D',"-.."},{'E',"."},{'F',"..-."},{'G',"--."},{'H',"...."},{'I',".."},{'J',".---"},{'K',"-.-"},{'L',".-.."},{'M',"--"},{'N',"-."},{'O',"---"},{'P',".--."},{'Q',"--.-"},{'R',".-."},{'S',"..."},{'T',"-"},{'U',"..-"},{'V',"...-"},{'W',".--"},{'X',"-..-"},{'Y',"-.--"},{'Z',"--.."}};if(message.empty()||message.front()==' '||message.back()==' ')return {};for(std::size_t i=0;i<message.size();++i)if((message[i]<'A'||message[i]>'Z')&&message[i]!=' ')return {};else if(message[i]==' '&&i>0&&message[i-1]==' ')return {};
std::string signal;for(std::size_t i=0;i<message.size();++i){if(message[i]==' '){signal.append(7,'_');continue;}const std::string& symbols=code.at(message[i]);for(std::size_t s=0;s<symbols.size();++s){signal.append(symbols[s]=='.'?1U:3U,'#');if(s+1<symbols.size())signal.push_back('_');}if(i+1<message.size()&&message[i+1]!=' ')signal.append(3,'_');}
MorseBanner out;out.valid=true;out.total_units=signal.size();out.mark_units=static_cast<std::size_t>(std::count(signal.begin(),signal.end(),'#'));out.rows.assign(2,std::string(signal.size(),' '));for(std::size_t i=0;i<signal.size();++i)out.rows[signal[i]=='#'?0:1][i]=signal[i]=='#'?'#':'_';return out;''',
        r'''auto z=render_morse_banner("A B");return !(z.valid&&z.rows[0]=="# ###       ### # # #"&&z.rows[1]==" _   _______   _ _ _ "&&z.mark_units==10&&z.total_units==21);''',
        r'''auto z=render_morse_banner("ET");if(!z.valid||z.rows[0]!="#   ###"||z.rows[1]!=" ___   "||z.mark_units!=4||z.total_units!=7)return 1;return render_morse_banner("").valid||render_morse_banner(" A").valid||render_morse_banner("A  B").valid||render_morse_banner("a").valid;''',
        "signal.append(7,'_')",
        "signal.append(4,'_')",
        "using only four low units between adjacent words",
        ("morse-codebook", "variable-mark-duration", "hierarchical-gap-units", "two-level-timeline"),
    ),
    Case(
        "woven-crossing-lattice",
        "Woven crossing lattice",
        "alternating warp-over and weft-over crossings across independently spaced strands",
        "struct WeaveLattice { std::vector<std::string> rows; std::size_t crossings = 0; std::size_t warp_over = 0; bool valid = false; };",
        "WeaveLattice",
        "weave_crossing_lattice",
        "std::size_t rows, std::size_t cols, std::size_t warp_spacing, std::size_t weft_spacing",
        "Dimensions are in [1,64], spacings are positive and no larger than their axes. Warp strands occupy columns divisible by warp_spacing; weft strands occupy rows divisible by weft_spacing. Empty cells are dot, warp-only vertical bar, weft-only hyphen. At crossings alternate X for warp-over and O for weft-over by parity of the strand indices. Count crossings and X cells.",
        r'''if(rows==0||cols==0||rows>64||cols>64||warp_spacing==0||weft_spacing==0||warp_spacing>cols||weft_spacing>rows)return {};WeaveLattice out;out.valid=true;out.rows.assign(rows,std::string(cols,'.'));
for(std::size_t r=0;r<rows;++r)for(std::size_t c=0;c<cols;++c){const bool warp=c%warp_spacing==0,weft=r%weft_spacing==0;if(warp&&weft){const bool over=((c/warp_spacing)+(r/weft_spacing))%2==0;out.rows[r][c]=over?'X':'O';++out.crossings;out.warp_over+=over;}else if(warp)out.rows[r][c]='|';else if(weft)out.rows[r][c]='-';}
return out;''',
        r'''auto z=weave_crossing_lattice(3,5,2,2);return !(z.valid&&z.rows==std::vector<std::string>{"X-O-X","|.|.|","O-X-O"}&&z.crossings==6&&z.warp_over==3);''',
        r'''auto z=weave_crossing_lattice(1,1,1,1);if(!z.valid||z.rows!=std::vector<std::string>{"X"}||z.crossings!=1||z.warp_over!=1)return 1;return weave_crossing_lattice(0,1,1,1).valid||weave_crossing_lattice(2,2,3,1).valid||weave_crossing_lattice(2,2,1,0).valid;''',
        "%2==0",
        "%2!=0",
        "reversing the documented over-under parity at every crossing",
        ("orthogonal-strand-placement", "crossing-index-parity", "four-cell-alphabet", "warp-over-ledger"),
    ),
    Case(
        "paperfold-dragon-raster",
        "Paperfold dragon raster",
        "generating paperfold turns by index parity and tracing the resulting right-angle path",
        "struct DragonRaster { std::vector<std::string> rows; std::size_t segments = 0; std::size_t left_turns = 0; bool valid = false; };",
        "DragonRaster",
        "raster_paperfold_dragon",
        "unsigned order",
        "Orders zero through ten are valid. The path has 2^order unit segments and starts east at (0,0). After segment i (one-based, before the final segment), compute lowbit=i&-i; turn left exactly when (i & (lowbit<<1)) is zero, otherwise right. Mark every visited lattice point and return the tight bounding box. Order zero has one segment and no turns.",
        r'''if(order>10)return {};const std::size_t segments=static_cast<std::size_t>(1)<<order;int row=0,col=0,direction=0;const int dr[4]={0,1,0,-1},dc[4]={1,0,-1,0};std::set<std::pair<int,int>> points{{0,0}};DragonRaster out;out.segments=segments;
for(std::size_t i=1;i<=segments;++i){row+=dr[direction];col+=dc[direction];points.insert({row,col});if(i<segments){const std::size_t low=i&(~i+1);const bool left=(i&(low<<1))==0;out.left_turns+=left;direction=left?(direction+3)%4:(direction+1)%4;}}
int min_r=points.begin()->first,max_r=min_r,min_c=points.begin()->second,max_c=min_c;for(auto point:points){min_r=std::min(min_r,point.first);max_r=std::max(max_r,point.first);min_c=std::min(min_c,point.second);max_c=std::max(max_c,point.second);}out.rows.assign(static_cast<std::size_t>(max_r-min_r+1),std::string(static_cast<std::size_t>(max_c-min_c+1),'.'));for(auto point:points)out.rows[static_cast<std::size_t>(point.first-min_r)][static_cast<std::size_t>(point.second-min_c)]='#';out.valid=true;return out;''',
        r'''auto z=raster_paperfold_dragon(1);return !(z.valid&&z.rows==std::vector<std::string>{".#","##"}&&z.segments==2&&z.left_turns==1);''',
        r'''auto z=raster_paperfold_dragon(0);if(!z.valid||z.rows!=std::vector<std::string>{"##"}||z.segments!=1||z.left_turns!=0)return 1;auto three=raster_paperfold_dragon(3);if(!three.valid||three.segments!=8||three.left_turns==0)return 1;return raster_paperfold_dragon(11).valid;''',
        "const bool left=(i&(low<<1))==0",
        "const bool left=(i&(low<<1))!=0",
        "inverting the paperfold bit test and mirroring every turn",
        ("paperfold-lowbit", "implicit-turn-sequence", "right-angle-trace", "visited-point-bounds"),
    ),
    Case(
        "axial-hex-ascii-map",
        "Axial hex ASCII map",
        "projecting unique axial hex coordinates onto a staggered monospaced canvas",
        "struct HexCell { int q = 0; int r = 0; char symbol = ' '; }; struct HexAsciiMap { std::vector<std::string> rows; int min_projected_column = 0; int min_r = 0; bool valid = false; };",
        "HexAsciiMap",
        "render_axial_hex_map",
        "const std::vector<HexCell>& cells",
        "cells is nonempty; q,r are in [-32,32], symbols are printable non-space, and coordinates are unique. Project axial (q,r) to row=r and column=2*q+r. Translate the minimum projected row/column to zero, preserving interior spaces and row order. The result field min_projected_column is exactly the pre-translation minimum of 2*q+r, while min_r is the minimum axial r. Duplicate coordinates invalidate the complete result.",
        r'''if(cells.empty())return {};std::set<std::pair<int,int>> used;int min_r=cells[0].r,max_r=min_r,min_c=2*cells[0].q+cells[0].r,max_c=min_c;for(auto cell:cells){if(cell.q<-32||cell.q>32||cell.r<-32||cell.r>32||cell.symbol<'!'||cell.symbol>'~'||!used.insert({cell.q,cell.r}).second)return {};const int projected=2*cell.q+cell.r;min_r=std::min(min_r,cell.r);max_r=std::max(max_r,cell.r);min_c=std::min(min_c,projected);max_c=std::max(max_c,projected);}HexAsciiMap out;out.valid=true;out.min_projected_column=min_c;out.min_r=min_r;out.rows.assign(static_cast<std::size_t>(max_r-min_r+1),std::string(static_cast<std::size_t>(max_c-min_c+1),' '));for(auto cell:cells)out.rows[static_cast<std::size_t>(cell.r-min_r)][static_cast<std::size_t>(2*cell.q+cell.r-min_c)]=cell.symbol;return out;''',
        r'''auto z=render_axial_hex_map({{-1,2,'A'},{0,0,'B'}});return !(z.valid&&z.rows==std::vector<std::string>{"B"," ","A"}&&z.min_projected_column==0&&z.min_r==0);''',
        r'''auto z=render_axial_hex_map({{0,0,'A'},{1,0,'B'},{0,1,'C'}});if(!z.valid||z.rows!=std::vector<std::string>{"A B"," C "}||z.min_projected_column!=0||z.min_r!=0)return 1;auto shifted=render_axial_hex_map({{-2,4,'X'},{-1,-2,'Y'}});if(!shifted.valid||shifted.min_projected_column!=-4||shifted.min_r!=-2)return 1;return render_axial_hex_map({}).valid||render_axial_hex_map({{0,0,'A'},{0,0,'B'}}).valid||render_axial_hex_map({{33,0,'A'}}).valid||render_axial_hex_map({{0,0,' '}}).valid;''',
        "out.min_projected_column=min_c",
        "out.min_projected_column=cells[0].q;for(auto cell:cells)out.min_projected_column=std::min(out.min_projected_column,cell.q)",
        "reporting minimum axial q instead of the documented projected-column origin",
        ("axial-coordinate-projection", "staggered-columns", "coordinate-uniqueness", "translated-bounds"),
    ),
    Case(
        "dot-matrix-marquee-clip",
        "Dot-matrix marquee clip",
        "composing caller-supplied glyph matrices and clipping a signed scrolling viewport",
        "struct MarqueeFrame { std::vector<std::string> rows; std::size_t source_width = 0; std::size_t visible_ink = 0; bool valid = false; };",
        "MarqueeFrame",
        "clip_dot_matrix_marquee",
        "const std::map<char, std::vector<std::string>>& glyphs, const std::string& message, std::size_t viewport_width, int offset",
        "glyphs and message are nonempty, viewport_width is in [1,80], glyph keys are printable non-space, and every glyph is a nonempty equal-height rectangular dot/hash matrix. Every message byte must exist. Compose glyphs left-to-right with one blank separator but no trailing separator. Source coordinate x shown at viewport column c is x=offset+c; coordinates outside the source are blank. Count visible hashes and report the unclipped source width.",
        r'''if(glyphs.empty()||message.empty()||viewport_width==0||viewport_width>80)return {};std::size_t height=0;for(const auto& item:glyphs){if(item.first<'!'||item.first>'~'||item.second.empty()||item.second.front().empty())return {};if(height==0)height=item.second.size();if(item.second.size()!=height)return {};const std::size_t width=item.second.front().size();for(const auto& row:item.second){if(row.size()!=width)return {};for(char ch:row)if(ch!='.'&&ch!='#')return {};}}std::vector<std::string> source(height);for(std::size_t i=0;i<message.size();++i){auto found=glyphs.find(message[i]);if(found==glyphs.end())return {};if(i!=0)for(auto& row:source)row.push_back('.');for(std::size_t r=0;r<height;++r)source[r]+=found->second[r];}MarqueeFrame out;out.valid=true;out.source_width=source.front().size();out.rows.assign(height,std::string(viewport_width,'.'));
for(std::size_t r=0;r<height;++r)for(std::size_t c=0;c<viewport_width;++c){const long x=static_cast<long>(offset)+static_cast<long>(c);if(x>=0&&x<static_cast<long>(out.source_width)){out.rows[r][c]=source[r][static_cast<std::size_t>(x)];out.visible_ink+=out.rows[r][c]=='#';}}return out;''',
        r'''auto z=clip_dot_matrix_marquee({{'A',{"#.","##"}},{'B',{"##","#."}}},"AB",4,1);return !(z.valid&&z.source_width==5&&z.rows==std::vector<std::string>{"..##","#.#."}&&z.visible_ink==4);''',
        r'''auto z=clip_dot_matrix_marquee({{'X',{"#"}}},"X",3,-1);if(!z.valid||z.rows!=std::vector<std::string>{".#."}||z.visible_ink!=1)return 1;return clip_dot_matrix_marquee({},"X",2,0).valid||clip_dot_matrix_marquee({{'X',{}}},"X",2,0).valid||clip_dot_matrix_marquee({{'X',{"#"}}},"Y",2,0).valid||clip_dot_matrix_marquee({{'X',{"#"}}},"X",0,0).valid;''',
        "static_cast<long>(offset)+static_cast<long>(c)",
        "static_cast<long>(c)-static_cast<long>(offset)",
        "moving the source opposite to the documented signed viewport offset",
        ("glyph-source-composition", "signed-viewport-clip", "caller-supplied-font", "visible-ink-ledger"),
    ),
)


assert len(CASES) == 20
assert len({case.task_id for case in CASES}) == len(CASES)
assert len({witness for case in CASES for witness in case.profile}) == 80


# Model-facing prose for `.docs/introduction.md` and the worked example inside
# `.docs/instructions.md`, keyed by task id. Every value in an example matches
# the case's own visible assertions. Keep this prose free of harness vocabulary
# and aligned with the official exercise documentation register.
INTRODUCTIONS: dict[str, str] = {
    "sierpinski-carpet-stencil": (
        "The Sierpinski carpet is a fractal made by repeatedly punching the "
        "middle square out of a grid: divide into thirds, remove the center, "
        "and repeat inside every remaining square. Fabric stencils, antenna "
        "plates, and quilt blocks all use the same recursive removal idea. "
        "Drawing one by hand means deciding, for every cell, whether any round "
        "of division removed it."
    ),
    "elementary-rule-tape": (
        "Elementary cellular automata show how a one-line rule can turn a "
        "single row of cells into anything from still life to chaos. Each new "
        "generation depends only on the three cells directly above, and the "
        "256 possible rules are catalogued by a single byte. Simulating a few "
        "generations of a chosen rule is the classic way to see its "
        "personality."
    ),
    "l-system-turtle-plot": (
        "Lindenmayer systems were invented to describe how plants branch: "
        "rewrite every symbol of a string in parallel, then read the result "
        "as drawing commands. Combined with a turtle that can save and return "
        "to earlier poses, a tiny grammar unfolds into ferns, trees, and "
        "fractal curves. Plotting the result on a character grid makes the "
        "growth visible."
    ),
    "bayer-threshold-mosaic": (
        "Before printers had gray ink, newspapers rendered photographs as "
        "patterns of black dots. Ordered dithering compares each pixel "
        "against a small repeating threshold matrix, so smooth shades become "
        "a stable mosaic of dark and light cells. The 2x2 Bayer matrix is the "
        "smallest classic example of such a matrix."
    ),
    "bresenham-segment-raster": (
        "Plotting a straight line on a grid of cells sounds easy until "
        "rounding makes it jagged or skips positions. Bresenham's algorithm "
        "walks the grid using only integer arithmetic, tracking a signed "
        "error term to decide each step. It remains the standard way to "
        "rasterize segments on everything from plotters to terminal "
        "interfaces."
    ),
    "midpoint-ellipse-raster": (
        "Circles and ellipses have to become blocky approximations on any "
        "discrete canvas. The midpoint method chooses each next boundary "
        "cell by testing where the true curve passes between two candidates, "
        "then mirrors the result across both axes. It draws smooth symmetric "
        "outlines without floating-point square roots in the inner loop."
    ),
    "scanline-polygon-raster": (
        "Filling a polygon on a pixel grid is the bread and butter of 2D "
        "graphics. The scanline method sweeps horizontal lines through the "
        "shape, pairs up the edge crossings, and fills the spans between "
        "them. Working with integer vertices and cell centers keeps the "
        "result exact and reproducible."
    ),
    "cubic-bezier-raster": (
        "Cubic Bezier curves are the workhorse of font outlines and vector "
        "drawing tools: four control points bend a smooth path between them. "
        "To show one on a character grid, the curve is sampled at regular "
        "parameter steps and the rounded positions are plotted. Watching the "
        "samples march along the curve also reveals how the control points "
        "pull it."
    ),
    "signed-histogram-baseline": (
        "Ledger balances, temperature anomalies, and score swings all go "
        "both positive and negative. A signed histogram plants a zero axis "
        "in the middle and grows bars upward or downward from it, so gains "
        "and losses share one readable picture. Keeping the baseline "
        "explicit makes the zero columns visible too."
    ),
    "crossword-start-numbering": (
        "Every published crossword numbers its squares so solvers can match "
        "clues to entries. A square earns a number when an across or down "
        "entry starts there, and the numbers march row by row through the "
        "grid. Reproducing that numbering from a blocked grid is the first "
        "step in any crossword construction tool."
    ),
    "nonogram-clue-gutters": (
        "Nonograms, also known as picross, hide a picture behind run-length "
        "clues along every row and column. The clues list the lengths of the "
        "consecutive filled blocks, and the solver works back from them. "
        "Building the clue margins from a finished bitmap is the reverse "
        "direction of the same puzzle."
    ),
    "terminal-overstrike-buffer": (
        "Old line printers and teletypes could revisit the row they were on: "
        "carriage return went back to the margin, backspace shuffled one "
        "column left, and bold text was simply typed twice in the same "
        "cell. Modeling a page as a fixed grid and replaying a byte stream "
        "captures exactly what such hardware would print."
    ),
    "ansi-visible-column-map": (
        "Terminal emulators let programs color their output with escape "
        "sequences that occupy no space on screen. That makes aligning "
        "colored text tricky: the byte offset of a character is no longer "
        "its visible column. Stripping the color commands while remembering "
        "where each visible character came from keeps both views in sync."
    ),
    "box-drawing-junction-map": (
        "Text-mode interfaces draw boxes and pipelines from simple glyphs: "
        "vertical bars, hyphens, and corners. Given a grid where each cell "
        "declares which of its four sides connect, the right glyph falls "
        "out of the connection pattern. Checking that both ends of every "
        "link agree keeps the drawing from dangling."
    ),
    "vertical-seam-carve": (
        "Seam carving resizes images by removing one winding path of "
        "low-energy pixels at a time instead of squashing everything. The "
        "cheapest vertical path is found with a small dynamic program over "
        "an energy map. Removing exactly that seam leaves every other byte "
        "of the picture untouched."
    ),
    "morse-timing-banner": (
        "Morse code is a timing protocol: dots and dashes last one and "
        "three units, and the silences between them are just as "
        "standardized. Rendering a message as a two-row strip of mark and "
        "gap units turns the rhythm into something you can see. Radio "
        "clubs still print such strips when teaching the code."
    ),
    "woven-crossing-lattice": (
        "Weaving alternates warp strands running down with weft strands "
        "running across, and each crossing shows whichever strand lies on "
        "top. A plain weave alternates over and under in a checkerboard "
        "rhythm. Spacing the strands out on a grid and marking the "
        "crossings produces the same lattice a loom card encodes."
    ),
    "paperfold-dragon-raster": (
        "Fold a strip of paper in half again and again, then unfold it to "
        "right angles: the crease pattern traces the dragon curve, a famous "
        "self-similar fractal. The direction of each turn falls out of "
        "simple bit arithmetic on its position. Drawing the path on a grid "
        "shows the curve's unmistakable spiral arms."
    ),
    "axial-hex-ascii-map": (
        "Hexagonal grids power strategy games and honeycomb maps, and axial "
        "coordinates address them with just two integers. Printing such a "
        "map on a monospaced terminal means projecting the skewed hex "
        "lattice onto staggered character cells. Anchoring the projection "
        "at a known corner keeps different maps comparable."
    ),
    "dot-matrix-marquee-clip": (
        "Dot-matrix signs scroll messages past a fixed window of lamps, "
        "showing only a slice of a much wider bitmap. Each letter is a "
        "small matrix of on and off dots, composed side by side into one "
        "long strip. Clipping a shifted window out of that strip is exactly "
        "what the sign's controller does."
    ),
}

EXAMPLES: dict[str, str] = {
    "sierpinski-carpet-stencil": (
        "Calling `cut_sierpinski_carpet(1, '#', '.')` returns `valid == true` "
        "with `ink_cells == 8` and rows:\n\n"
        "```text\n###\n#.#\n###\n```"
    ),
    "elementary-rule-tape": (
        "Calling `evolve_elementary_rule(\".#.\", 30, 3)` returns "
        "`valid == true` with `live_cells == 5` and generations:\n\n"
        "```text\n.#.\n###\n#..\n```"
    ),
    "l-system-turtle-plot": (
        "Calling `plot_l_system(\"F\", {{'F', \"F+F\"}}, 1)` rewrites the "
        "stream to `F+F`, then draws it: the turtle marks (0,0), steps east, "
        "turns clockwise, and marks (1,1). The result is `valid == true` "
        "with `forward_steps == 2`, `expanded_symbols == 3`, and rows:\n\n"
        "```text\n##\n.#\n```"
    ),
    "bayer-threshold-mosaic": (
        "Calling `dither_bayer2({{0, 255}, {128, 64}}, '#', '.')` compares "
        "each intensity with the repeated threshold matrix [[0,128],[192,64]] "
        "and returns `valid == true` with `dark_cells == 3` and rows:\n\n"
        "```text\n#.\n##\n```"
    ),
    "bresenham-segment-raster": (
        "Calling `raster_segment({0, 0}, {2, 1}, '#')` returns "
        "`valid == true` with `plotted == 3`, `origin == {0, 0}`, and "
        "rows:\n\n```text\n#..\n.##\n```"
    ),
    "midpoint-ellipse-raster": (
        "Calling `raster_midpoint_ellipse(2, 1, '#')` returns "
        "`valid == true` with `boundary_cells == 8` and rows:\n\n"
        "```text\n.###.\n#...#\n.###.\n```"
    ),
    "scanline-polygon-raster": (
        "Calling `fill_polygon_scanlines({{0, 0}, {3, 0}, {0, 3}}, '#')` "
        "fills the triangle's cell centers and returns `valid == true` with "
        "`filled == 3`, `origin == {0, 0}`, and rows:\n\n"
        "```text\n##.\n#..\n...\n```"
    ),
    "cubic-bezier-raster": (
        "Calling `raster_cubic_bezier({0, 0}, {3, 0}, {3, 3}, {0, 3}, 5)` "
        "samples five points, keeps the unique lattice positions "
        "(0,0), (2,0), (2,2), (2,3), (0,3) in `samples`, and returns "
        "`valid == true` with rows:\n\n```text\n#.#\n...\n..#\n#.#\n```"
    ),
    "signed-histogram-baseline": (
        "Calling `plot_signed_histogram({2, 0, -1}, 2)` returns "
        "`valid == true` with `positive_cells == 2`, `negative_cells == 1`, "
        "and rows:\n\n```text\n^  \n^  \n+0+\n  v\n   \n```"
    ),
    "crossword-start-numbering": (
        "Calling `number_crossword_starts({\"..#\", \"...\", \"#..\"})` "
        "returns `valid == true` with `next_number == 6`, numbers "
        "{{1,2,0},{3,0,4},{0,5,0}}, and display:\n\n"
        "```text\n0102##\n03..04\n##05..\n```"
    ),
    "nonogram-clue-gutters": (
        "Calling `build_nonogram_gutters({\"#.#\", \"###\"})` returns "
        "`valid == true` with `row_clues == {\"1,1\", \"3\"}`, "
        "`column_clues == {\"2\", \"1\", \"2\"}`, `max_row_runs == 2`, and "
        "`max_column_runs == 1`."
    ),
    "terminal-overstrike-buffer": (
        r'Calling `print_overstrike_stream(1, 4, "AB\bC")` writes `A` and '
        r"`B`, steps one column left, and overwrites the `B` with `C`. The "
        "result is `valid == true` with `cursor_col == 2`, "
        "`overwritten == 1`, and one row:\n\n```text\nAC  \n```"
    ),
    "ansi-visible-column-map": (
        r'Calling `map_ansi_visible_columns("A\x1b[31mB\x1b[0m\tC", 4)` '
        r"strips both SGR sequences and expands the tab at column 1 to the "
        "next strict tab-stop boundary. It returns `valid == true` with "
        "`columns == {0, 1, 2, 3, 4}`, both tab-expanded spaces mapped back "
        "to the tab byte, and text:\n\n```text\nAB  C\n```"
    ),
    "box-drawing-junction-map": (
        "Calling `render_junction_map({{6, 12}, {3, 9}})` sees a small loop: "
        "every cell is a two-way turn, so the result is `valid == true` with "
        "`endpoints == 0`, `junctions == 0`, and rows:\n\n"
        "```text\n++\n++\n```"
    ),
    "vertical-seam-carve": (
        "Calling `carve_vertical_seam({\"ab\", \"cd\"}, {{1, 1}, {1, 1}})` "
        "finds a flat tie and keeps the leftmost seam. It returns "
        "`valid == true` with `seam_columns == {0, 0}`, `total_energy == 2`, "
        "and rows:\n\n```text\nb\nd\n```"
    ),
    "morse-timing-banner": (
        "Calling `render_morse_banner(\"A B\")` encodes `.-` and `-...` "
        "around a seven-unit word gap and returns `valid == true` with "
        "`mark_units == 10`, `total_units == 21`, and rows:\n\n"
        "```text\n# ###       ### # # #\n _   _______   _ _ _ \n```"
    ),
    "woven-crossing-lattice": (
        "Calling `weave_crossing_lattice(3, 5, 2, 2)` lays warp strands on "
        "columns 0, 2, 4 and weft strands on rows 0 and 2, alternating the "
        "top strand. It returns `valid == true` with `crossings == 6`, "
        "`warp_over == 3`, and rows:\n\n```text\nX-O-X\n|.|.|\nO-X-O\n```"
    ),
    "paperfold-dragon-raster": (
        "Calling `raster_paperfold_dragon(1)` draws two segments with one "
        "left turn and returns `valid == true` with `segments == 2`, "
        "`left_turns == 1`, and rows:\n\n```text\n.#\n##\n```"
    ),
    "axial-hex-ascii-map": (
        "Calling `render_axial_hex_map({{-1, 2, 'A'}, {0, 0, 'B'}})` "
        "projects `B` to row 0, column 0 and `A` to row 2, column 0, so "
        "nothing shifts. It returns `valid == true` with "
        "`min_projected_column == 0`, `min_r == 0`, and rows:\n\n"
        "```text\nB\n \nA\n```"
    ),
    "dot-matrix-marquee-clip": (
        "Calling `clip_dot_matrix_marquee({{'A', {\"#.\", \"##\"}}, "
        "{'B', {\"##\", \"#.\"}}}, \"AB\", 4, 1)` composes a five-column "
        "source strip, then shows source columns 1 through 4. It returns "
        "`valid == true` with `source_width == 5`, `visible_ink == 4`, and "
        "rows:\n\n```text\n..##\n#.#.\n```"
    ),
}


assert set(INTRODUCTIONS) == {case.task_id for case in CASES}
assert set(EXAMPLES) == {case.task_id for case in CASES}
