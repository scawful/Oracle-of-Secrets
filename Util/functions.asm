function RGBto555(R,G,B) = ((R/8)<<10)|((G/8)<<5)|(B/8) ; zarby 
function hexto555(h) = ((((h&$FF)/8)<<10)|(((h>>8&$FF)/8)<<5)|(((h>>16&$FF)/8)<<0)) ; kan 
function menu_offset(y,x) = (y*64)+(x*2)