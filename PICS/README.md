# CBM viewer demo

`alex.png` was supplied by the user for the viewer demo. Its 101x72 source is
unchanged. `ALEX.CBM` is the aspect-fitted, 88x63, Floyd-Steinberg monochrome
conversion (704 bytes, including the 11-byte header):

```sh
python3 tools/png_to_cbm.py PICS/alex.png PICS/ALEX.CBM --width 88 --height 63 --dither
python3 tools/png_to_cbm.py PICS/clockwork.png PICS/CLOCKWORK.CBM --width 96 --height 58 --dither
python3 tools/png_to_cbm.py PICS/alex2.jpg PICS/ALEX2.CBM --width 56 --height 61 --dither
```

`clockwork.png` is the second user-supplied source (1020x612), also unchanged.
`CLOCKWORK.CBM` is its 96x58 aspect-fitted dithered conversion (707 bytes).
`alex2.jpg` is the third user-supplied source (794x869), unchanged.
`ALEX2.CBM` is its 56x61 dithered conversion (438 bytes). This smaller demo
leaves retained-display space for `xclock &` and `xwave &` simultaneously.
The larger original conversions remain unchanged. Any pair of these three
pictures fits the shared display pool; larger pictures plus other apps may not.
The packed viewer retains these three images in 701, 704 and 435 bytes,
respectively, independent of pixel density. `tools/build_xview_demo.py` also
generates **ALEX128.CBM (128x80)** and **CLOCK160.CBM (160x100)** into its new
output directory without changing the source images or original conversions.
They use 1,288 and 2,008 retained bytes. Test the 160x100 picture alone.
See
[the format and viewer instructions](../abi/cbm.md) for packaging a **new**
demo disk. No source license or ownership is inferred from the supplied images.
