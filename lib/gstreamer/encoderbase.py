###
### Copyright (C) 2018-2021 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

import os
import slash

from ...lib.common import timefn, get_media, call
from ...lib.gstreamer.util import have_gst, have_gst_element
from ...lib.metrics import md5, calculate_psnr
from ...lib.parameters import format_value
from ...lib.util import skip_test_if_missing_features

@slash.requires(have_gst)
@slash.requires(*have_gst_element("checksumsink2"))
class BaseEncoderTest(slash.Test):
  def before(self):
    self.refctx = []

  def map_profile(self):
    raise NotImplementedError

  def map_best_hw_format(self):
    raise NotImplementedError

  def map_format(self):
    raise NotImplementedError

  def map_formatu(self):
    raise NotImplementedError

  def gen_encoder_opts(self):
    raise NotImplementedError

  def get_file_ext(self):
    raise NotImplementedError

  def gen_input_opts(self):
    opts = "filesrc location={source} num-buffers={frames}"
    opts += " ! rawvideoparse format={mformat} width={width} height={height}"
    if vars(self).get("fps", None) is not None:
      opts += " framerate={fps}"
    opts += " ! videoconvert chroma-mode=none dither=0 ! video/x-raw,format={hwformat}"

    return opts

  def gen_output_opts(self):
    opts = "{gstencoder} "
    opts += self.gen_encoder_opts()
    opts += " ! {gstmediatype}"
    if vars(self).get("profile", None) is not None:
      opts += ",profile={mprofile}"
    if vars(self).get("gstparser", None) is not None:
      opts += " ! {gstparser}"
    if vars(self).get("gstmuxer", None) is not None:
      opts += " ! {gstmuxer}"
    opts += " ! filesink location={encoded}"

    return opts

  def gen_name(self):
    name = "{case}-{rcmode}"
    if vars(self).get("profile", None) is not None:
      name += "-{profile}"
    if vars(self).get("fps", None) is not None:
      name += "-{fps}"
    if vars(self).get("gop", None) is not None:
      name += "-{gop}"
    if vars(self).get("qp", None) is not None:
      name += "-{qp}"
    if vars(self).get("slices", None) is not None:
      name += "-{slices}"
    if vars(self).get("quality", None) is not None:
      name += "-{quality}"
    if vars(self).get("bframes", None) is not None:
      name += "-{bframes}"
    if vars(self).get("minrate", None) is not None:
      name += "-{minrate}k"
    if vars(self).get("maxrate", None) is not None:
      name += "-{maxrate}k"
    if vars(self).get("refmode", None) is not None:
      name += "-{refmode}"
    if vars(self).get("refs", None) is not None:
      name += "-{refs}"
    if vars(self).get("lowpower", False):
      name += "-low-power"
    if vars(self).get("loopshp", None) is not None:
      name += "-{loopshp}"
    if vars(self).get("looplvl", None) is not None:
      name += "-{looplvl}"
    if vars(self).get("ladepth", None) is not None:
      name += "-{ladepth}"
    if vars(self).get("r2r", None) is not None:
      name += "-r2r"

    return name

  @timefn("gst")
  def call_gst(self, iopts, oopts):
    self.output = call("gst-launch-1.0 -vf {iopts} ! {oopts}".format(
      iopts = iopts, oopts = oopts))

  def validate_caps(self):
    skip_test_if_missing_features(self)

    self.hwformat = self.map_best_hw_format()
    self.mformat  = self.map_format()
    self.mformatu = self.map_formatu()

    if None in [self.hwformat, self.mformatu]:
      slash.skip_test("{format} format not supported".format(**vars(self)))

    maxw, maxh = self.caps["maxres"]
    if self.width > maxw or self.height > maxh:
      slash.skip_test(
        format_value(
          "{platform}.{driver}.{width}x{height} not supported", **vars(self)))

    if vars(self).get("slices", 1) > 1 and not self.caps.get("multislice", True):
      slash.skip_test(
        format_value(
          "{platform}.{driver}.slice > 1 unsupported in this mode", **vars(self)))

    if not self.caps.get(self.rcmode, True):
      slash.skip_test(
        format_value(
          "{platform}.{driver}.{rcmode} unsupported in this mode", **vars(self)))

    if vars(self).get("profile", None) is not None:
      self.mprofile = self.map_profile()
      if self.mprofile is None:
        slash.skip_test("{profile} profile is not supported".format(**vars(self)))

  def encode(self):
    self.validate_caps()

    get_media().test_call_timeout = vars(self).get("call_timeout", 0)

    iopts = self.gen_input_opts()
    oopts = self.gen_output_opts()
    name  = self.gen_name().format(**vars(self))
    ext   = self.get_file_ext()

    self.encoded = get_media()._test_artifact("{}.{}".format(name, ext))
    self.call_gst(iopts.format(**vars(self)), oopts.format(**vars(self)))

    if vars(self).get("r2r", None) is not None:
      assert type(self.r2r) is int and self.r2r > 1, "invalid r2r value"
      md5ref = md5(self.encoded)
      get_media()._set_test_details(md5_ref = md5ref)
      for i in range(1, self.r2r):
        self.encoded = get_media()._test_artifact("{}_{}.{}".format(name, i, ext))
        self.call_gst(iopts.format(**vars(self)), oopts.format(**vars(self)))
        result = md5(self.encoded)
        get_media()._set_test_details(**{"md5_{:03}".format(i): result})
        assert md5ref == result, "r2r md5 mismatch"
        # delete encoded file after each iteration
        get_media()._purge_test_artifact(self.encoded)
    else:
      self.check_bitrate()
      self.check_metrics()

  def check_metrics(self):
    iopts = "filesrc location={encoded} ! {gstdecoder}"
    oopts = (
      "videoconvert chroma-mode=none dither=0 ! video/x-raw,format={mformatu} ! checksumsink2"
      " file-checksum=false frame-checksum=false plane-checksum=false"
      " dump-output=true qos=false dump-location={decoded} eos-after={frames}")
    name = (self.gen_name() + "-{width}x{height}-{format}").format(**vars(self))

    self.decoded = get_media()._test_artifact("{}.yuv".format(name))
    self.call_gst(iopts.format(**vars(self)), oopts.format(**vars(self)))

    get_media().baseline.check_psnr(
      psnr = calculate_psnr(
        self.source, self.decoded,
        self.width, self.height,
        self.frames, self.format),
      context = self.refctx,
    )

  def check_bitrate(self):
    encsize = os.path.getsize(self.encoded)
    bitrate_actual = encsize * 8 * vars(self).get("fps", 25) / 1024.0 / self.frames
    get_media()._set_test_details(
      size_encoded = encsize,
      bitrate_actual = "{:-.2f}".format(bitrate_actual))

    if "cbr" == self.rcmode:
      bitrate_gap = abs(bitrate_actual - self.bitrate) / self.bitrate
      get_media()._set_test_details(bitrate_gap = "{:.2%}".format(bitrate_gap))

      # acceptable bitrate within 10% of bitrate
      assert(bitrate_gap <= 0.10)

    elif self.rcmode in ["vbr", "la_vbr"]:
      # acceptable bitrate within 25% of minrate and 10% of maxrate
      assert(self.minrate * 0.75 <= bitrate_actual <= self.maxrate * 1.10)
