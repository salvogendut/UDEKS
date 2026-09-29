struct scene_case { unsigned int x; unsigned char y; unsigned int width; unsigned char height,flags; };
static const struct scene_case cases[8] = {{0,0,16,18,0},{303,182,17,18,13},{0,0,48,48,1},{256,96,64,104,15},{150,96,168,104,13},{0,0,320,200,13},{10,10,100,100,13},{220,100,100,100,13}};
static const unsigned int expected[8] = {49629u,45346u,1790u,64949u,64211u,8171u,57u,57329u};
