from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    title: str
    objective: str
    types: str
    return_type: str
    function: str
    params: str
    body: str
    visible: str
    hidden: str
    prompt_terms: tuple[str, ...]
    profile: tuple[str, ...]


@dataclass(frozen=True)
class NegativeMutation:
    description: str
    old: str
    new: str


CASES = (
    Case(
        "scale-archive-stamps", "scale-archive-stamps", "Archive stamp enlargement",
        "nearest-neighbor enlargement with an unscaled whitespace margin",
        "struct StampReport { std::vector<std::string> rows; std::size_t nonblank = 0; bool valid = false; };",
        "StampReport", "scale_archive_stamps",
        "const std::vector<std::string>& grid, std::size_t horizontal, std::size_t vertical, std::size_t margin",
        r'''if (grid.empty() || grid.front().empty() || horizontal == 0 || vertical == 0) return {};
const std::size_t cols = grid.front().size();
for (const auto& row : grid) if (row.size() != cols) return {};
const std::size_t cap = std::numeric_limits<std::size_t>::max();
if (cols > (cap - 2 * margin) / horizontal || grid.size() > (cap - 2 * margin) / vertical) return {};
StampReport out; out.valid = true;
const std::size_t width = cols * horizontal + 2 * margin;
out.rows.assign(margin, std::string(width, ' '));
for (const auto& row : grid) {
  std::string scaled(margin, ' ');
  for (char cell : row) { scaled.append(horizontal, cell); if (cell != ' ') out.nonblank += horizontal * vertical; }
  scaled.append(margin, ' ');
  for (std::size_t copy = 0; copy < vertical; ++copy) out.rows.push_back(scaled);
}
out.rows.insert(out.rows.end(), margin, std::string(width, ' ')); return out;''',
        r'''auto z = scale_archive_stamps({"# "}, 2, 1, 1);
return !(z.valid && z.rows == std::vector<std::string>{"      ", " ##   ", "      "} && z.nonblank == 2);''',
        r'''auto z = scale_archive_stamps({"A", " "}, 1, 2, 0);
if (!z.valid || z.rows != std::vector<std::string>{"A", "A", " ", " "} || z.nonblank != 2) return 1;
return scale_archive_stamps({"x", "yy"}, 2, 2, 0).valid || scale_archive_stamps({"x"}, 0, 1, 0).valid;''',
        ("margin", "horizontal", "vertical", "nonblank"),
        ("nearest-neighbor", "margin-frame", "rectangular-grid", "anisotropic"),
    ),
    Case(
        "scale-cave-warning", "nine-slice-cave-frame", "Nine-slice cave frame",
        "nine-slice stretching that preserves corners and stretches edges and center independently",
        "struct FrameReport { std::vector<std::string> rows; std::size_t interior_area = 0; bool valid = false; };",
        "FrameReport", "stretch_cave_frame",
        "const std::vector<std::string>& frame, std::size_t target_rows, std::size_t target_cols",
        r'''if (frame.size() < 3 || frame.front().size() < 3 || target_rows < frame.size() || target_cols < frame.front().size()) return {};
const std::size_t source_cols = frame.front().size(); for (const auto& row : frame) if (row.size() != source_cols) return {};
FrameReport out; out.valid = true; out.interior_area = (target_rows - 2) * (target_cols - 2);
out.rows.assign(target_rows, std::string(target_cols, ' '));
auto map_axis = [](std::size_t p, std::size_t target, std::size_t source) { if (p == 0) return std::size_t{0}; if (p + 1 == target) return source - 1; return 1 + (p - 1) * (source - 2) / (target - 2); };
for (std::size_t r = 0; r < target_rows; ++r) for (std::size_t c = 0; c < target_cols; ++c) out.rows[r][c] = frame[map_axis(r,target_rows,frame.size())][map_axis(c,target_cols,source_cols)];
return out;''',
        r'''auto z = stretch_cave_frame({"+-+", "|.|", "+-+"}, 5, 5);
return !(z.valid && z.rows.front() == "+---+" && z.rows.back() == "+---+" && z.rows[2] == "|...|" && z.interior_area == 9);''',
        r'''auto z = stretch_cave_frame({"abcd", "e..f", "g..h", "ijkl"}, 5, 6);
if (!z.valid || z.rows.size() != 5 || z.rows[0].front() != 'a' || z.rows[0].back() != 'd' || z.rows.back().front() != 'i') return 1;
return stretch_cave_frame({"ab", "cd"}, 4, 4).valid || stretch_cave_frame({"abc", "de", "fgh"}, 4, 4).valid;''',
        ("nine-slice", "corners", "edges", "interior"),
        ("nine-slice", "corner-preserving", "axis-map", "frame"),
    ),
    Case(
        "scale-circuit-icons", "connector-grid-dilation", "Connector dilation",
        "Manhattan-radius dilation from connector cells while preserving authoritative symbols",
        "struct Coordinate { std::size_t row = 0; std::size_t col = 0; }; struct ConnectorReport { std::vector<std::string> rows; std::vector<Coordinate> changed; bool valid = false; };",
        "ConnectorReport", "dilate_connectors",
        "const std::vector<std::string>& grid, std::size_t radius",
        r'''if (grid.empty() || grid.front().empty() || radius == 0) return {}; const std::size_t cols = grid.front().size(); for (const auto& row : grid) if (row.size() != cols) return {};
ConnectorReport out; out.rows = grid; out.valid = true;
for (std::size_t r = 0; r < grid.size(); ++r) for (std::size_t c = 0; c < cols; ++c) if (grid[r][c] == '.') {
  bool near = false; for (std::size_t rr = 0; rr < grid.size() && !near; ++rr) for (std::size_t cc = 0; cc < cols; ++cc) if (grid[rr][cc] == '+' && (rr > r ? rr-r : r-rr) + (cc > c ? cc-c : c-cc) <= radius) { near = true; break; }
  if (near) { out.rows[r][c] = '*'; out.changed.push_back({r,c}); }
} return out;''',
        r'''auto z = dilate_connectors({"...", ".+.", "..."}, 1);
return !(z.valid && z.rows == std::vector<std::string>{".*.", "*+*", ".*."} && z.changed.size() == 4);''',
        r'''auto z = dilate_connectors({"+X.", "..."}, 2);
if (!z.valid || z.rows[0][1] != 'X' || z.rows[1][1] != '*') return 1;
return dilate_connectors({}, 1).valid || dilate_connectors({"..", "."}, 1).valid || dilate_connectors({"+"}, 0).valid;''',
        ("Manhattan", "connector", "radius", "row-major"),
        ("dilation", "manhattan-ball", "preserve-symbols", "changed-coordinates"),
    ),
    Case(
        "scale-evacuation-signs", "route-map-aspect-fit", "Route map aspect fit",
        "largest-integer aspect-preserving fit centered in a fixed box",
        "struct FitReport { std::vector<std::string> rows; std::size_t scale = 0; std::size_t top = 0; std::size_t left = 0; bool valid = false; };",
        "FitReport", "fit_route_map",
        "const std::vector<std::string>& grid, std::size_t box_rows, std::size_t box_cols",
        r'''if (grid.empty() || grid.front().empty()) return {}; const std::size_t cols = grid.front().size(); for (const auto& row : grid) if (row.size() != cols) return {};
const std::size_t scale = std::min(box_rows / grid.size(), box_cols / cols); if (scale == 0) return {};
FitReport out; out.valid = true; out.scale = scale; out.top = (box_rows-grid.size()*scale)/2; out.left=(box_cols-cols*scale)/2; out.rows.assign(box_rows,std::string(box_cols,'.'));
for (std::size_t r=0;r<grid.size();++r) for(std::size_t c=0;c<cols;++c) for(std::size_t y=0;y<scale;++y) for(std::size_t x=0;x<scale;++x) out.rows[out.top+r*scale+y][out.left+c*scale+x]=grid[r][c]; return out;''',
        r'''auto z = fit_route_map({"AB"}, 4, 6);
return !(z.valid && z.scale == 3 && z.top == 0 && z.left == 0 && z.rows[2] == "AAABBB" && z.rows[3] == "......");''',
        r'''auto z = fit_route_map({"ab", "cd"}, 5, 7);
if (!z.valid || z.scale != 2 || z.top != 0 || z.left != 1 || z.rows[4] != ".......") return 1;
return fit_route_map({"abc"}, 1, 2).valid || fit_route_map({"a", "bb"}, 3, 3).valid;''',
        ("largest", "aspect", "center", "offset"),
        ("aspect-fit", "letterbox-scale", "integer-scale", "centering"),
    ),
    Case(
        "scale-factory-status", "status-panel-decimator", "Status panel decimation",
        "phase-zero row and column stride decimation",
        "struct PanelReport { std::vector<std::string> rows; std::size_t alerts = 0; bool valid = false; };",
        "PanelReport", "decimate_status_panel",
        "const std::vector<std::string>& grid, std::size_t row_stride, std::size_t col_stride",
        r'''if (grid.empty() || grid.front().empty() || row_stride == 0 || col_stride == 0) return {}; const std::size_t cols=grid.front().size(); for(const auto& row:grid) if(row.size()!=cols) return {};
PanelReport out; out.valid=true; for(std::size_t r=0;r<grid.size();r+=row_stride){ std::string row; for(std::size_t c=0;c<cols;c+=col_stride){row.push_back(grid[r][c]); if(grid[r][c]=='A') ++out.alerts;} out.rows.push_back(row);} return out;''',
        r'''auto z = decimate_status_panel({"A12", "345", "6A8"}, 2, 2);
return !(z.valid && z.rows == std::vector<std::string>{"A2", "68"} && z.alerts == 1);''',
        r'''auto z = decimate_status_panel({"ABCD", "EFGH"}, 1, 3);
if (!z.valid || z.rows != std::vector<std::string>{"AD", "EH"}) return 1;
return decimate_status_panel({"x"},0,1).valid || decimate_status_panel({"x","yy"},1,1).valid;''',
        ("stride", "phase-zero", "decimate", "alerts"),
        ("subsampling", "stride-grid", "phase-zero", "downscale"),
    ),
    Case(
        "scale-flood-warning", "flood-map-majority-downsample", "Flood majority downsample",
        "complete-block majority reduction with an explicit tie symbol",
        "struct Block { std::size_t row = 0; std::size_t col = 0; }; struct FloodReport { std::vector<std::string> rows; std::vector<Block> ties; bool valid = false; };",
        "FloodReport", "downsample_flood_map",
        "const std::vector<std::string>& grid, std::size_t block_rows, std::size_t block_cols",
        r'''if(grid.empty()||grid.front().empty()||block_rows==0||block_cols==0||grid.size()%block_rows!=0) return {}; const std::size_t cols=grid.front().size(); for(const auto& row:grid) if(row.size()!=cols) return {}; if(cols%block_cols!=0) return {};
FloodReport out; out.valid=true; for(std::size_t br=0;br<grid.size()/block_rows;++br){std::string row; for(std::size_t bc=0;bc<cols/block_cols;++bc){std::size_t wet=0; for(std::size_t y=0;y<block_rows;++y) for(std::size_t x=0;x<block_cols;++x) wet += grid[br*block_rows+y][bc*block_cols+x]=='#'; const std::size_t area=block_rows*block_cols; char ch=wet*2>area?'#':(wet*2==area?'~':'.'); row.push_back(ch); if(ch=='~') out.ties.push_back({br,bc});} out.rows.push_back(row);} return out;''',
        r'''auto z = downsample_flood_map({"##..", "#..."}, 2, 2);
return !(z.valid && z.rows == std::vector<std::string>{"#."} && z.ties.empty());''',
        r'''auto z = downsample_flood_map({"#.", ".#"},2,2); if(!z.valid||z.rows!=std::vector<std::string>{"~"}||z.ties.size()!=1) return 1;
return downsample_flood_map({"###"},1,2).valid || downsample_flood_map({"#"},0,1).valid;''',
        ("strict majority", "tie", "divisible", "complete blocks"),
        ("block-reduction", "majority", "tie-diagnostic", "downsample"),
    ),
    Case(
        "scale-game-minimap", "minimap-viewport-zoom", "Minimap viewport zoom",
        "bounded square viewport extraction followed by integer enlargement",
        "struct ZoomReport { std::vector<std::string> rows; std::size_t source_top = 0; std::size_t source_left = 0; bool valid = false; };",
        "ZoomReport", "zoom_minimap",
        "const std::vector<std::string>& grid, std::size_t center_row, std::size_t center_col, std::size_t radius, std::size_t factor",
        r'''if(grid.empty()||grid.front().empty()||factor==0) return {}; const std::size_t cols=grid.front().size(); for(const auto& row:grid) if(row.size()!=cols) return {}; if(center_row>=grid.size()||center_col>=cols||radius>center_row||radius>center_col||center_row+radius>=grid.size()||center_col+radius>=cols) return {};
ZoomReport out; out.valid=true; out.source_top=center_row-radius; out.source_left=center_col-radius; for(std::size_t r=out.source_top;r<=center_row+radius;++r){std::string wide; for(std::size_t c=out.source_left;c<=center_col+radius;++c) wide.append(factor,grid[r][c]); for(std::size_t y=0;y<factor;++y) out.rows.push_back(wide);} return out;''',
        r'''auto z = zoom_minimap({"abc", "def", "ghi"},1,1,1,2);
return !(z.valid && z.rows.size()==6 && z.rows[0]=="aabbcc" && z.rows[5]=="gghhii" && z.source_top==0);''',
        r'''auto z=zoom_minimap({"01234","56789","abcde","fghij","klmno"},2,2,1,1); if(!z.valid||z.rows!=std::vector<std::string>{"678","bcd","ghi"}||z.source_left!=1) return 1;
return zoom_minimap({"ab","cd"},0,0,1,2).valid || zoom_minimap({"x"},0,0,0,0).valid;''',
        ("viewport", "center", "radius", "source top-left"),
        ("crop-then-scale", "bounded-window", "center-radius", "zoom"),
    ),
    Case(
        "scale-garden-plans", "garden-tile-repeat", "Garden tile repetition",
        "whole-tile repetition in two dimensions",
        "struct GardenReport { std::vector<std::string> rows; std::size_t plant_cells = 0; bool valid = false; };",
        "GardenReport", "repeat_garden_tile",
        "const std::vector<std::string>& tile, std::size_t tile_rows, std::size_t tile_cols",
        r'''if(tile.empty()||tile.front().empty()||tile_rows==0||tile_cols==0) return {}; const std::size_t cols=tile.front().size(); for(const auto& row:tile) if(row.size()!=cols) return {}; GardenReport out; out.valid=true;
for(std::size_t tr=0;tr<tile_rows;++tr) for(const auto& source:tile){std::string row; for(std::size_t tc=0;tc<tile_cols;++tc) row+=source; out.plant_cells+=static_cast<std::size_t>(std::count(row.begin(),row.end(),'P')); out.rows.push_back(row);} return out;''',
        r'''auto z=repeat_garden_tile({"P.", ".P"},2,2); return !(z.valid&&z.rows.size()==4&&z.rows[0]=="P.P."&&z.rows[2]=="P.P."&&z.plant_cells==8);''',
        r'''auto z=repeat_garden_tile({"ab"},1,3); if(!z.valid||z.rows!=std::vector<std::string>{"ababab"}) return 1; return repeat_garden_tile({},1,1).valid||repeat_garden_tile({"x"},0,1).valid;''',
        ("whole tile", "tile rows", "tile columns", "plant cells"),
        ("mosaic-repeat", "whole-pattern", "two-axis-count", "tiling"),
    ),
    Case(
        "scale-harbor-flags", "flag-stripe-resampler", "Flag stripe resampling",
        "largest-remainder proportional allocation of stripe widths",
        "struct Stripe { char symbol = ' '; std::size_t width = 0; }; struct FlagReport { std::string row; std::vector<std::size_t> allocated; bool valid = false; };",
        "FlagReport", "resample_flag_stripes",
        "const std::vector<Stripe>& stripes, std::size_t target_width",
        r'''if(stripes.empty()||target_width==0) return {}; std::size_t total=0; for(std::size_t i=0;i<stripes.size();++i){if(stripes[i].width==0||(i&&stripes[i-1].symbol==stripes[i].symbol)) return {}; total+=stripes[i].width;} FlagReport out; out.valid=true; out.allocated.assign(stripes.size(),0); std::vector<std::pair<std::size_t,std::size_t>> rem;
std::size_t used=0; for(std::size_t i=0;i<stripes.size();++i){const std::size_t product=target_width*stripes[i].width; out.allocated[i]=product/total; used+=out.allocated[i]; rem.push_back({product%total,i});} std::stable_sort(rem.begin(),rem.end(),[](auto a,auto b){return a.first>b.first;}); for(std::size_t k=0;k<target_width-used;++k) ++out.allocated[rem[k].second]; for(std::size_t i=0;i<stripes.size();++i) out.row.append(out.allocated[i],stripes[i].symbol); return out;''',
        r'''auto z=resample_flag_stripes({{'R',1},{'W',2},{'B',1}},6); return !(z.valid&&z.allocated==std::vector<std::size_t>{2,3,1}&&z.row=="RRWWWB");''',
        r'''auto z=resample_flag_stripes({{'A',1},{'B',1},{'C',1}},2); if(!z.valid||z.allocated!=std::vector<std::size_t>{1,1,0}||z.row!="AB") return 1; return resample_flag_stripes({{'A',1},{'A',2}},3).valid||resample_flag_stripes({},3).valid;''',
        ("largest remainder", "fractional", "source-order ties", "allocated widths"),
        ("proportional-allocation", "largest-remainder", "stripe-records", "tie-break"),
    ),
    Case(
        "scale-lab-plate-map", "plate-coordinate-expander", "Plate coordinate expansion",
        "sparse sample coordinates expanded into labeled square wells",
        "struct Sample { std::size_t row = 0; std::size_t col = 0; char label = '.'; }; struct PlateReport { std::vector<std::string> rows; std::vector<Sample> origins; bool valid = false; };",
        "PlateReport", "expand_plate_samples",
        "std::size_t rows, std::size_t cols, const std::vector<Sample>& samples, std::size_t factor",
        r'''if(rows==0||cols==0||factor==0) return {}; std::set<std::pair<std::size_t,std::size_t>> seen; for(const auto& s:samples) if(s.row>=rows||s.col>=cols||s.label=='.'||!seen.insert({s.row,s.col}).second) return {}; PlateReport out; out.valid=true; out.rows.assign(rows*factor,std::string(cols*factor,'.'));
for(const auto& s:samples){out.origins.push_back({s.row*factor,s.col*factor,s.label}); for(std::size_t y=0;y<factor;++y) for(std::size_t x=0;x<factor;++x) out.rows[s.row*factor+y][s.col*factor+x]=s.label;} return out;''',
        r'''auto z=expand_plate_samples(2,2,{{0,1,'A'},{1,0,'B'}},2); return !(z.valid&&z.rows==std::vector<std::string>{"..AA","..AA","BB..","BB.."}&&z.origins[1].row==2);''',
        r'''auto z=expand_plate_samples(1,3,{{0,2,'X'}},1); if(!z.valid||z.rows!=std::vector<std::string>{"..X"}) return 1; return expand_plate_samples(2,2,{{0,0,'A'},{0,0,'B'}},2).valid||expand_plate_samples(1,1,{{1,0,'A'}},1).valid;''',
        ("sparse samples", "unique coordinates", "origins", "factor-square"),
        ("sparse-to-dense", "labeled-coordinates", "square-expansion", "input-order"),
    ),
    Case(
        "scale-museum-wayfinding", "wayfinding-letterbox", "Wayfinding letterbox",
        "centered padding without resampling",
        "struct Door { std::size_t row = 0; std::size_t col = 0; }; struct SignReport { std::vector<std::string> rows; std::vector<Door> doors; bool valid = false; };",
        "SignReport", "letterbox_sign",
        "const std::vector<std::string>& grid, std::size_t target_rows, std::size_t target_cols, char blank",
        r'''if(grid.empty()||grid.front().empty()||blank=='\0'||target_rows<grid.size()||target_cols<grid.front().size()) return {}; const std::size_t cols=grid.front().size(); for(const auto& row:grid) if(row.size()!=cols) return {}; SignReport out; out.valid=true; out.rows.assign(target_rows,std::string(target_cols,blank)); const std::size_t top=(target_rows-grid.size())/2,left=(target_cols-cols)/2;
for(std::size_t r=0;r<grid.size();++r) for(std::size_t c=0;c<cols;++c){out.rows[top+r][left+c]=grid[r][c]; if(grid[r][c]=='D') out.doors.push_back({top+r,left+c});} return out;''',
        r'''auto z=letterbox_sign({"D>"},3,4,'.'); return !(z.valid&&z.rows==std::vector<std::string>{"....",".D>.","...."}&&z.doors[0].col==1);''',
        r'''auto z=letterbox_sign({"ab","cD"},4,5,'_'); if(!z.valid||z.rows[1].substr(1,2)!="ab"||z.doors[0].row!=2) return 1; return letterbox_sign({"abc"},1,2,'.').valid||letterbox_sign({"a","bb"},3,3,'.').valid;''',
        ("letterbox", "no resampling", "floor offsets", "door coordinates"),
        ("padding-only", "centering", "door-diagnostic", "canvas"),
    ),
    Case(
        "scale-orchard-layout", "orchard-sparse-expander", "Orchard irrigation bands",
        "ordered insertion of irrigation rows and columns in original coordinates",
        "struct OrchardReport { std::vector<std::string> rows; std::size_t irrigation_area = 0; bool valid = false; };",
        "OrchardReport", "insert_irrigation_bands",
        "const std::vector<std::string>& grid, const std::vector<std::size_t>& after_rows, const std::vector<std::size_t>& after_cols, std::size_t band_width",
        r'''if(grid.empty()||grid.front().empty()||band_width==0) return {}; const std::size_t cols=grid.front().size(); for(const auto& row:grid) if(row.size()!=cols) return {}; auto ordered=[](const auto& xs,std::size_t bound){for(std::size_t i=0;i<xs.size();++i) if(xs[i]>=bound||(i&&xs[i-1]>=xs[i])) return false; return true;}; if(!ordered(after_rows,grid.size())||!ordered(after_cols,cols)) return {};
OrchardReport out; out.valid=true; const std::size_t width=cols+after_cols.size()*band_width; for(std::size_t r=0;r<grid.size();++r){std::string row; for(std::size_t c=0;c<cols;++c){row.push_back(grid[r][c]); if(std::binary_search(after_cols.begin(),after_cols.end(),c)) row.append(band_width,'I');} out.rows.push_back(row); if(std::binary_search(after_rows.begin(),after_rows.end(),r)) for(std::size_t k=0;k<band_width;++k) out.rows.push_back(std::string(width,'I'));} for(const auto& row:out.rows) out.irrigation_area+=static_cast<std::size_t>(std::count(row.begin(),row.end(),'I')); return out;''',
        r'''auto z=insert_irrigation_bands({"TT",".."},{0},{0},1); return !(z.valid&&z.rows==std::vector<std::string>{"TIT","III",".I."}&&z.irrigation_area==5);''',
        r'''auto z=insert_irrigation_bands({"ab"},{},{},2); if(!z.valid||z.rows!=std::vector<std::string>{"ab"}||z.irrigation_area!=0) return 1; return insert_irrigation_bands({"x"},{0,0},{},1).valid||insert_irrigation_bands({"x"},{},{1},1).valid;''',
        ("original coordinates", "irrigation bands", "strictly increasing", "crossings"),
        ("band-insertion", "coordinate-remap", "row-precedence", "ordered-indices"),
    ),
    Case(
        "scale-quilt-preview", "quilt-block-magnifier", "Quilt block magnifier",
        "token-aware rasterization of a rectangular block matrix",
        "struct PaletteCount { char symbol = ' '; std::size_t cells = 0; }; struct QuiltReport { std::vector<std::string> rows; std::vector<PaletteCount> palette; bool valid = false; };",
        "QuiltReport", "magnify_quilt",
        "const std::vector<std::vector<std::string>>& blocks, std::size_t block_height, std::size_t block_width",
        r'''if(blocks.empty()||blocks.front().empty()||block_height==0||block_width==0) return {}; const std::size_t cols=blocks.front().size(); std::map<char,std::size_t> counts; for(const auto& row:blocks){if(row.size()!=cols) return {}; for(const auto& token:row) if(token.size()!=1) return {};}
QuiltReport out; out.valid=true; for(const auto& source:blocks){std::string row; for(const auto& token:source){row.append(block_width,token[0]); counts[token[0]]+=block_height*block_width;} for(std::size_t y=0;y<block_height;++y) out.rows.push_back(row);} for(auto [symbol,cells]:counts) out.palette.push_back({symbol,cells}); return out;''',
        r'''auto z=magnify_quilt({{{"A"},{"B"}}},2,3); return !(z.valid&&z.rows==std::vector<std::string>{"AAABBB","AAABBB"}&&z.palette.size()==2&&z.palette[0].cells==6);''',
        r'''auto z=magnify_quilt({{{"Z"}},{{"Z"}}},1,2); if(!z.valid||z.palette[0].cells!=4) return 1; return magnify_quilt({{{"AA"}}},2,2).valid||magnify_quilt({},1,1).valid;''',
        ("one-character tokens", "block height", "block width", "palette order"),
        ("token-raster", "block-matrix", "ordered-histogram", "magnify"),
    ),
    Case(
        "scale-radar-glyphs", "radar-center-anchored-scale", "Radar ring resampling",
        "symmetric center-anchored resampling with Chebyshev-ring diagnostics",
        "struct RadarReport { std::vector<std::string> rows; std::vector<std::size_t> contacts_per_ring; bool valid = false; };",
        "RadarReport", "resample_radar_rings",
        "const std::vector<std::string>& grid, std::size_t target_radius",
        r'''if(grid.empty()||grid.size()%2==0||grid.front().size()!=grid.size()||target_radius==0) return {}; for(const auto& row:grid) if(row.size()!=grid.size()) return {}; const std::size_t source_radius=grid.size()/2; if(grid[source_radius][source_radius]!='@') return {}; RadarReport out; out.valid=true; const std::size_t side=2*target_radius+1; out.rows.assign(side,std::string(side,'.')); out.contacts_per_ring.assign(target_radius+1,0);
auto map_offset=[&](long d){const long sign=d<0?-1:1; const std::size_t a=static_cast<std::size_t>(d<0?-d:d); return sign*static_cast<long>((a*source_radius+target_radius/2)/target_radius);}; for(std::size_t r=0;r<side;++r) for(std::size_t c=0;c<side;++c){long sr=static_cast<long>(source_radius)+map_offset(static_cast<long>(r)-static_cast<long>(target_radius)); long sc=static_cast<long>(source_radius)+map_offset(static_cast<long>(c)-static_cast<long>(target_radius)); char ch=grid[static_cast<std::size_t>(sr)][static_cast<std::size_t>(sc)]; out.rows[r][c]=ch; if(ch!='.') ++out.contacts_per_ring[std::max(r>target_radius?r-target_radius:target_radius-r,c>target_radius?c-target_radius:target_radius-c)];} return out;''',
        r'''auto z=resample_radar_rings({"a.b",".@.","c.d"},1); return !(z.valid&&z.rows==std::vector<std::string>{"a.b",".@.","c.d"}&&z.contacts_per_ring[0]==1);''',
        r'''auto z=resample_radar_rings({"x.x",".@.","x.x"},2); if(!z.valid||z.rows.size()!=5||z.rows[2][2]!='@'||z.contacts_per_ring.size()!=3) return 1; return resample_radar_rings({"..",".."},2).valid||resample_radar_rings({"...","...","..."},1).valid;''',
        ("Chebyshev ring", "geometric center", "symmetric rounding", "contacts per ring"),
        ("ring-resample", "center-anchor", "symmetric-map", "ring-histogram"),
    ),
    Case(
        "scale-school-seating", "seating-aisle-preserving-scale", "Aisle-preserving seating scale",
        "selective horizontal scaling in which aisle columns retain unit width",
        "struct SeatingReport { std::vector<std::string> rows; std::vector<std::size_t> aisle_columns; bool valid = false; };",
        "SeatingReport", "scale_seating_with_aisles",
        "const std::vector<std::string>& grid, std::size_t seat_factor, std::size_t row_factor",
        r'''if(grid.empty()||grid.front().empty()||seat_factor==0||row_factor==0) return {}; const std::size_t cols=grid.front().size(); for(const auto& row:grid) if(row.size()!=cols) return {}; SeatingReport out; std::string first; for(char ch:grid.front()){if(ch=='/'){out.aisle_columns.push_back(first.size()); first.push_back(ch);}else first.append(seat_factor,ch);} if(out.aisle_columns.empty()) return {}; out.valid=true;
for(const auto& source:grid){std::string row; for(char ch:source) { if(ch=='/') row.push_back(ch); else row.append(seat_factor,ch); } for(std::size_t y=0;y<row_factor;++y) out.rows.push_back(row);} return out;''',
        r'''auto z=scale_seating_with_aisles({"S/S"},2,2); return !(z.valid&&z.rows==std::vector<std::string>{"SS/SS","SS/SS"}&&z.aisle_columns==std::vector<std::size_t>{2});''',
        r'''auto z=scale_seating_with_aisles({"A//B"},3,1); if(!z.valid||z.rows[0]!="AAA//BBB"||z.aisle_columns!=std::vector<std::size_t>{3,4}) return 1; return scale_seating_with_aisles({"SS"},2,2).valid||scale_seating_with_aisles({"/"},0,1).valid;''',
        ("aisle", "unit width", "seat factor", "aisle columns"),
        ("selective-scale", "delimiter-preserve", "column-remap", "seating"),
    ),
    Case(
        "scale-ski-trail-map", "trail-polyline-raster-scale", "Trail polyline raster scale",
        "orthogonal polyline coordinate scaling and tight-grid rasterization",
        "struct Point { long row = 0; long col = 0; }; struct TrailReport { std::vector<std::string> rows; std::size_t path_length = 0; bool valid = false; };",
        "TrailReport", "rasterize_scaled_trail",
        "const std::vector<Point>& vertices, std::size_t factor",
        r'''if(vertices.size()<2||factor==0) return {}; for(const auto& p:vertices) if(p.row<0||p.col<0) return {}; std::vector<Point> path; for(std::size_t i=1;i<vertices.size();++i){long r1=vertices[i-1].row*static_cast<long>(factor),c1=vertices[i-1].col*static_cast<long>(factor),r2=vertices[i].row*static_cast<long>(factor),c2=vertices[i].col*static_cast<long>(factor); if((r1==r2)==(c1==c2)) return {}; long dr=(r2>r1)-(r2<r1),dc=(c2>c1)-(c2<c1); if(path.empty()) path.push_back({r1,c1}); while(r1!=r2||c1!=c2){r1+=dr;c1+=dc;path.push_back({r1,c1});}}
long minr=path[0].row,maxr=minr,minc=path[0].col,maxc=minc; for(auto p:path){minr=std::min(minr,p.row);maxr=std::max(maxr,p.row);minc=std::min(minc,p.col);maxc=std::max(maxc,p.col);} TrailReport out; out.valid=true; out.path_length=path.size(); out.rows.assign(static_cast<std::size_t>(maxr-minr+1),std::string(static_cast<std::size_t>(maxc-minc+1),'.')); for(auto p:path) out.rows[static_cast<std::size_t>(p.row-minr)][static_cast<std::size_t>(p.col-minc)]='#'; return out;''',
        r'''auto z=rasterize_scaled_trail({{0,0},{0,2},{1,2}},1); return !(z.valid&&z.rows==std::vector<std::string>{"###","..#"}&&z.path_length==4);''',
        r'''auto z=rasterize_scaled_trail({{1,1},{3,1}},2); if(!z.valid||z.rows.size()!=5||z.path_length!=5) return 1; return rasterize_scaled_trail({{0,0},{1,1}},1).valid||rasterize_scaled_trail({{0,0}},1).valid;''',
        ("orthogonal", "vertices", "lattice points", "tight grid"),
        ("polyline-raster", "coordinate-scale", "join-dedup", "bounding-box"),
    ),
    Case(
        "scale-solar-dashboard", "solar-palette-quantizer", "Solar palette quantizer",
        "area-bucket horizontal resampling over ordered palette indices",
        "struct SymbolCount { char symbol = ' '; std::size_t count = 0; }; struct SolarReport { std::vector<std::string> rows; std::vector<SymbolCount> counts; bool valid = false; };",
        "SolarReport", "quantize_solar_columns",
        "const std::vector<std::string>& grid, const std::string& palette, std::size_t target_cols",
        r'''if(grid.empty()||grid.front().empty()||palette.empty()||target_cols==0||target_cols>grid.front().size()) return {}; const std::size_t cols=grid.front().size(); std::set<char> unique(palette.begin(),palette.end()); if(unique.size()!=palette.size()) return {}; for(const auto& row:grid){if(row.size()!=cols) return {}; for(char ch:row) if(palette.find(ch)==std::string::npos) return {};} SolarReport out; out.valid=true; std::map<char,std::size_t> counts;
for(const auto& source:grid){std::string row; for(std::size_t b=0;b<target_cols;++b){std::size_t begin=b*cols/target_cols,end=(b+1)*cols/target_cols,sum=0; for(std::size_t c=begin;c<end;++c) sum+=palette.find(source[c]); char chosen=palette[sum/(end-begin)]; row.push_back(chosen); ++counts[chosen];} out.rows.push_back(row);} for(char ch:palette) out.counts.push_back({ch,counts[ch]}); return out;''',
        r'''auto z=quantize_solar_columns({"0123"},"0123",2); return !(z.valid&&z.rows==std::vector<std::string>{"02"}&&z.counts[0].count==1&&z.counts[2].count==1);''',
        r'''auto z=quantize_solar_columns({"333000"},"0123",3); if(!z.valid||z.rows!=std::vector<std::string>{"310"}) return 1; return quantize_solar_columns({"01"},"001",1).valid||quantize_solar_columns({"0x"},"01",1).valid;''',
        ("palette order", "area bucket", "average index", "target columns"),
        ("palette-quantize", "bucket-average", "horizontal-resample", "histogram"),
    ),
    Case(
        "scale-theater-backdrop", "backdrop-layer-compositor", "Backdrop layer compositor",
        "ordered transparent compositing followed by nearest-neighbor scaling",
        "struct Layer { std::vector<std::string> rows; }; struct BackdropReport { std::vector<std::string> rows; std::vector<std::size_t> visible_by_layer; bool valid = false; };",
        "BackdropReport", "compose_scaled_backdrop",
        "const std::vector<Layer>& layers, std::size_t factor, char transparent",
        r'''if(layers.empty()||factor==0||transparent=='\0'||layers.front().rows.empty()||layers.front().rows.front().empty()) return {}; const std::size_t rows=layers.front().rows.size(),cols=layers.front().rows.front().size(); for(const auto& layer:layers){if(layer.rows.size()!=rows) return {}; for(const auto& row:layer.rows) if(row.size()!=cols) return {};} std::vector<std::string> composite(rows,std::string(cols,transparent)); std::vector<std::vector<std::size_t>> owner(rows,std::vector<std::size_t>(cols,layers.size()));
for(std::size_t i=0;i<layers.size();++i) for(std::size_t r=0;r<rows;++r) for(std::size_t c=0;c<cols;++c) if(layers[i].rows[r][c]!=transparent){composite[r][c]=layers[i].rows[r][c];owner[r][c]=i;} BackdropReport out; out.valid=true; out.visible_by_layer.assign(layers.size(),0); for(std::size_t r=0;r<rows;++r){std::string wide; for(std::size_t c=0;c<cols;++c){wide.append(factor,composite[r][c]); if(owner[r][c]<layers.size()) out.visible_by_layer[owner[r][c]]+=factor*factor;} for(std::size_t y=0;y<factor;++y) out.rows.push_back(wide);} return out;''',
        r'''auto z=compose_scaled_backdrop({{{"AA"}},{{"B."}}},2,'.'); return !(z.valid&&z.rows==std::vector<std::string>{"BBAA","BBAA"}&&z.visible_by_layer==std::vector<std::size_t>{4,4});''',
        r'''auto z=compose_scaled_backdrop({{{"AA"}},{{"B."}}},1,'.'); if(!z.valid||z.rows!=std::vector<std::string>{"BA"}||z.visible_by_layer!=std::vector<std::size_t>{1,1}) return 1; return compose_scaled_backdrop({},2,'.').valid||compose_scaled_backdrop({{{"a"}},{{"bb"}}},1,'.').valid;''',
        ("transparent", "later layers", "visible by layer", "composite"),
        ("layer-composite", "ownership-grid", "scale-after-compose", "occlusion"),
    ),
    Case(
        "scale-warehouse-labels", "label-runlength-expander", "Run-length label expansion",
        "run-length decoding fused with anisotropic scaling",
        "struct Run { char symbol = ' '; std::size_t length = 0; }; struct LabelReport { std::vector<std::string> rows; std::size_t decoded_width = 0; bool valid = false; };",
        "LabelReport", "expand_label_runs",
        "const std::vector<std::vector<Run>>& rows, std::size_t horizontal, std::size_t vertical",
        r'''if(rows.empty()||horizontal==0||vertical==0) return {}; std::size_t width=0; LabelReport out; for(std::size_t r=0;r<rows.size();++r){std::size_t current=0; std::string decoded; for(auto run:rows[r]){if(run.length==0) return {}; current+=run.length; decoded.append(run.length*horizontal,run.symbol);} if(r==0) width=current; else if(current!=width) return {}; for(std::size_t y=0;y<vertical;++y) out.rows.push_back(decoded);} if(width==0) return {}; out.valid=true; out.decoded_width=width; return out;''',
        r'''auto z=expand_label_runs({{{'A',2},{'B',1}}},2,2); return !(z.valid&&z.rows==std::vector<std::string>{"AAAABB","AAAABB"}&&z.decoded_width==3);''',
        r'''auto z=expand_label_runs({{{'X',1}},{{'Y',1}}},1,1); if(!z.valid||z.rows!=std::vector<std::string>{"X","Y"}) return 1; return expand_label_runs({{{'A',0}}},1,1).valid||expand_label_runs({{{'A',1}},{{'B',2}}},1,1).valid;''',
        ("run length", "decoded width", "fused", "anisotropic"),
        ("rle-fused-scale", "run-records", "width-reconcile", "row-repeat"),
    ),
    Case(
        "scale-weather-symbols", "weather-frame-atlas-scale", "Weather frame atlas",
        "equal-frame enlargement and fixed-gutter atlas assembly",
        "struct Origin { std::size_t row = 0; std::size_t col = 0; }; struct AtlasReport { std::vector<std::string> rows; std::vector<Origin> origins; bool valid = false; };",
        "AtlasReport", "scale_weather_atlas",
        "const std::vector<std::vector<std::string>>& frames, std::size_t factor, std::size_t gutter",
        r'''if(frames.empty()||factor==0||frames.front().empty()||frames.front().front().empty()) return {}; const std::size_t rows=frames.front().size(),cols=frames.front().front().size(); for(const auto& frame:frames){if(frame.size()!=rows) return {}; for(const auto& row:frame) if(row.size()!=cols) return {};} AtlasReport out; out.valid=true; const std::size_t width=frames.size()*cols*factor+(frames.size()-1)*gutter; out.rows.assign(rows*factor,std::string(width,'.'));
for(std::size_t f=0;f<frames.size();++f){const std::size_t left=f*(cols*factor+gutter); out.origins.push_back({0,left}); for(std::size_t r=0;r<rows;++r) for(std::size_t c=0;c<cols;++c) for(std::size_t y=0;y<factor;++y) for(std::size_t x=0;x<factor;++x) out.rows[r*factor+y][left+c*factor+x]=frames[f][r][c];} return out;''',
        r'''auto z=scale_weather_atlas({{"S"},{"R"}},2,1); return !(z.valid&&z.rows==std::vector<std::string>{"SS.RR","SS.RR"}&&z.origins[1].col==3);''',
        r'''auto z=scale_weather_atlas({{"ab"},{"cd"}},1,0); if(!z.valid||z.rows!=std::vector<std::string>{"abcd"}||z.origins[1].col!=2) return 1; return scale_weather_atlas({},1,1).valid||scale_weather_atlas({{"a"},{"bb"}},1,1).valid;''',
        ("frames", "atlas", "gutter", "origins"),
        ("multi-frame-atlas", "equal-shape", "gutter-layout", "frame-origins"),
    ),
)


# Each false substitute is the complete independent reference with one
# task-specific semantic rule deliberately changed.  The owner requires the
# replacement site to occur exactly once, builds the result with the reference
# warning policy, and proves that the ordinary visible oracle rejects it.
NEGATIVE_MUTATIONS = {
    "scale-archive-stamps": NegativeMutation(
        "incorrectly scales the outer margin with the stamp",
        "const std::size_t width = cols * horizontal + 2 * margin;",
        "const std::size_t width = (cols + 2 * margin) * horizontal;",
    ),
    "nine-slice-cave-frame": NegativeMutation(
        "maps stretched interior cells into the outer source band",
        "return 1 + (p - 1) * (source - 2) / (target - 2);",
        "return (p - 1) * (source - 2) / (target - 2);",
    ),
    "connector-grid-dilation": NegativeMutation(
        "uses a Chebyshev square instead of a Manhattan ball",
        "(rr > r ? rr-r : r-rr) + (cc > c ? cc-c : c-cc) <= radius",
        "std::max((rr > r ? rr-r : r-rr), (cc > c ? cc-c : c-cc)) <= radius",
    ),
    "route-map-aspect-fit": NegativeMutation(
        "forces unit scale instead of selecting the largest integer fit",
        "const std::size_t scale = std::min(box_rows / grid.size(), box_cols / cols);",
        "const std::size_t scale = std::size_t{1};",
    ),
    "status-panel-decimator": NegativeMutation(
        "samples the last cell of each stride rather than phase zero",
        "for(std::size_t r=0;r<grid.size();r+=row_stride){ std::string row; for(std::size_t c=0;c<cols;c+=col_stride)",
        "for(std::size_t r=row_stride-1;r<grid.size();r+=row_stride){ std::string row; for(std::size_t c=col_stride-1;c<cols;c+=col_stride)",
    ),
    "flood-map-majority-downsample": NegativeMutation(
        "requires unanimous wet cells instead of a strict majority",
        "char ch=wet*2>area?'#':(wet*2==area?'~':'.');",
        "char ch=wet==area?'#':(wet*2==area?'~':'.');",
    ),
    "minimap-viewport-zoom": NegativeMutation(
        "anchors the crop at the center instead of the radius offset",
        "out.source_top=center_row-radius; out.source_left=center_col-radius;",
        "out.source_top=center_row; out.source_left=center_col;",
    ),
    "garden-tile-repeat": NegativeMutation(
        "magnifies cells instead of repeating the complete tile",
        "for(std::size_t tc=0;tc<tile_cols;++tc) row+=source;",
        "for(char cell : source) row.append(tile_cols, cell);",
    ),
    "flag-stripe-resampler": NegativeMutation(
        "awards residual columns to the smallest remainder",
        "return a.first>b.first;",
        "return a.first<b.first;",
    ),
    "plate-coordinate-expander": NegativeMutation(
        "marks only each scaled origin instead of its square well",
        "for(std::size_t y=0;y<factor;++y) for(std::size_t x=0;x<factor;++x) out.rows[s.row*factor+y][s.col*factor+x]=s.label;",
        "out.rows[s.row*factor][s.col*factor]=s.label;",
    ),
    "wayfinding-letterbox": NegativeMutation(
        "pins content to the upper-left instead of centering it",
        "const std::size_t top=(target_rows-grid.size())/2,left=(target_cols-cols)/2;",
        "const std::size_t top=0,left=0;",
    ),
    "orchard-sparse-expander": NegativeMutation(
        "leaves irrigation row crossings blank rather than irrigated",
        "out.rows.push_back(std::string(width,'I'));",
        "out.rows.push_back(std::string(width,'.'));",
    ),
    "quilt-block-magnifier": NegativeMutation(
        "uses block height as the horizontal token width",
        "row.append(block_width,token[0]);",
        "row.append(block_height,token[0]);",
    ),
    "radar-center-anchored-scale": NegativeMutation(
        "reflects offsets through the center during ring mapping",
        "return sign*static_cast<long>((a*source_radius+target_radius/2)/target_radius);",
        "return -sign*static_cast<long>((a*source_radius+target_radius/2)/target_radius);",
    ),
    "seating-aisle-preserving-scale": NegativeMutation(
        "widens aisle columns together with seats",
        "if(ch=='/') row.push_back(ch); else row.append(seat_factor,ch);",
        "if(ch=='/') row.append(seat_factor,ch); else row.append(seat_factor,ch);",
    ),
    "trail-polyline-raster-scale": NegativeMutation(
        "adds an extra scale unit to every polyline coordinate",
        "vertices[i-1].row*static_cast<long>(factor),c1=vertices[i-1].col*static_cast<long>(factor),r2=vertices[i].row*static_cast<long>(factor),c2=vertices[i].col*static_cast<long>(factor)",
        "vertices[i-1].row*static_cast<long>(factor+1),c1=vertices[i-1].col*static_cast<long>(factor+1),r2=vertices[i].row*static_cast<long>(factor+1),c2=vertices[i].col*static_cast<long>(factor+1)",
    ),
    "solar-palette-quantizer": NegativeMutation(
        "chooses each bucket's trailing sample instead of its average palette index",
        "char chosen=palette[sum/(end-begin)];",
        "char chosen=source[end-1];",
    ),
    "backdrop-layer-compositor": NegativeMutation(
        "composites in reverse order so earlier layers win",
        "for(std::size_t i=0;i<layers.size();++i)",
        "for(std::size_t i=layers.size();i-- > 0;)",
    ),
    "label-runlength-expander": NegativeMutation(
        "decodes run lengths without horizontal scaling",
        "decoded.append(run.length*horizontal,run.symbol);",
        "decoded.append(run.length,run.symbol);",
    ),
    "weather-frame-atlas-scale": NegativeMutation(
        "scales the fixed atlas gutter with each frame",
        "const std::size_t width=frames.size()*cols*factor+(frames.size()-1)*gutter;",
        "const std::size_t width=frames.size()*cols*factor+(frames.size()-1)*gutter*factor;",
    ),
}


PUBLIC_CONTRACTS = {
    "scale-archive-stamps": "The grid must be nonempty and rectangular and both scale factors must be positive. Repeat every cell horizontally and every source row vertically, then add exactly `margin` unscaled blank rows and columns. `nonblank` counts the repeated non-space cells.",
    "nine-slice-cave-frame": "The source must be rectangular and at least 3 by 3; each target dimension must be at least its source dimension. Preserve the four corner cells, map the first and last target rows and columns to their matching source edges, and proportionally map only the interior. `interior_area` is `(target_rows - 2) * (target_cols - 2)`.",
    "connector-grid-dilation": "The grid must be nonempty and rectangular and `radius` must be positive. Change only `.` cells whose Manhattan distance from any `+` connector is at most `radius`; write `*`, preserve every authoritative non-dot symbol, and list changed coordinates in row-major order.",
    "route-map-aspect-fit": "The grid must be nonempty and rectangular. Choose the largest positive integer scale that fits both box dimensions, center the scaled grid with floor offsets, and fill unused cells with `.`; a box too small for scale one is invalid.",
    "status-panel-decimator": "The grid must be nonempty and rectangular and both strides must be positive. Select source rows and columns beginning at index zero and then at each stride. `alerts` counts only selected `A` cells.",
    "flood-map-majority-downsample": "The grid must be nonempty and rectangular; block dimensions must be positive and divide the grid exactly. Emit `#` for a strict wet-cell majority, `.` for a strict dry majority, and `~` for a tie, listing tied output blocks in row-major order.",
    "minimap-viewport-zoom": "The grid must be nonempty and rectangular, `factor` must be positive, and the complete square from `center - radius` through `center + radius` must lie inside the source. Extract that viewport, enlarge every cell by `factor`, and report its source top-left coordinate; do not clamp an out-of-bounds viewport.",
    "garden-tile-repeat": "The tile must be nonempty and rectangular and both repetition counts must be positive. Repeat the complete source tile `tile_cols` times across and `tile_rows` times down; do not magnify individual cells. `plant_cells` counts `P` in the final mosaic.",
    "flag-stripe-resampler": "The stripe list and target width must be nonempty; every source width is positive and adjacent stripes may not share a symbol. Allocate floor proportional widths, then award leftover cells by descending fractional remainder with source-order ties. Return allocations in source order.",
    "plate-coordinate-expander": "Rows, columns, and factor must be positive. Every sample coordinate must be in bounds, unique, and use a label other than `.`. Paint each sample as a factor-by-factor square and report scaled origins in input order.",
    "wayfinding-letterbox": "The grid must be nonempty and rectangular, the blank byte must be non-null, and neither target dimension may be smaller than the source. Copy without resampling at floor-centered offsets, leaving any odd extra padding on the bottom or right, and list transformed `D` coordinates in row-major order.",
    "orchard-sparse-expander": "The grid must be nonempty and rectangular and band width must be positive. Row and column insertion indices are original-coordinate indices, strictly increasing, unique, and in bounds. Insert each irrigation band immediately after its named source row or column; crossings remain `I` and `irrigation_area` counts every final `I`.",
    "quilt-block-magnifier": "The block matrix must be nonempty and rectangular, both block dimensions must be positive, and every token must contain exactly one byte. Rasterize each token as a block-height by block-width rectangle and return palette counts in ascending symbol order.",
    "radar-center-anchored-scale": "The source must be a nonempty odd square with `@` at its geometric center and target radius must be positive. Map signed offsets symmetrically with nearest rounding around the fixed center and count non-dot output contacts by Chebyshev ring.",
    "seating-aisle-preserving-scale": "The grid must be nonempty and rectangular, both factors must be positive, and the first row must contain at least one `/` aisle. Repeat every non-aisle cell by `seat_factor`, keep every `/` at unit width, repeat rows by `row_factor`, and report transformed first-row aisle columns from left to right.",
    "trail-polyline-raster-scale": "At least two nonnegative vertices and a positive factor are required. Every consecutive pair must form a nonzero orthogonal segment. Scale vertex coordinates, enumerate every lattice point without duplicating joins, rasterize `#` in the tight bounding box, and report the enumerated path length.",
    "solar-palette-quantizer": "The grid must be nonempty and rectangular; the palette must be nonempty with unique bytes; every cell must occur in it; and target columns must be from one through the source width. Partition each row into floor-boundary nonempty buckets, average palette indices with integer floor, and return counts in palette order.",
    "backdrop-layer-compositor": "At least one nonempty rectangular layer, a positive factor, and a non-null transparent byte are required; every layer shape must match. Composite in input order so later opaque cells replace earlier ones, then enlarge the completed composite. `visible_by_layer` counts final scaled cells owned by each layer.",
    "label-runlength-expander": "At least one encoded row and positive horizontal and vertical factors are required. Every run length must be positive, every row must decode to the same positive width, each run expands horizontally by its length times the horizontal factor, and each decoded row repeats vertically. `decoded_width` is the unscaled common width.",
    "weather-frame-atlas-scale": "Frames must be nonempty, rectangular, and equal-shaped and factor must be positive. Enlarge each frame independently, place frames left-to-right, keep exactly `gutter` unscaled `.` columns between them, and report each frame origin in input order.",
}
