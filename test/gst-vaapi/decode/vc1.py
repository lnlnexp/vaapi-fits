###
### Copyright (C) 2018-2019 Intel Corporation
###
### SPDX-License-Identifier: BSD-3-Clause
###

from ....lib import *
from ....lib.gstreamer.vaapi.util import *
from ....lib.gstreamer.vaapi.decoder import DecoderTest

spec = load_test_spec("vc1", "decode")
spec_r2r = load_test_spec("vc1", "decode", "r2r")

@slash.requires(*platform.have_caps("decode", "vc1"))
@slash.requires(*have_gst_element("vaapivc1dec"))
class default(DecoderTest):
  def before(self):
    # default metric
    self.metric = dict(type = "ssim", miny = 0.99, minu = 0.99, minv = 0.99)
    self.caps   = platform.get_caps("decode", "vc1")
    super(default, self).before()

  @slash.parametrize(("case"), sorted(spec.keys()))
  def test(self, case):
    vars(self).update(spec[case].copy())
    vars(self).update(
      case        = case,
      gstdecoder  = "'video/x-wmv,profile=(string)advanced'"
                    ",width={width},height={height},framerate=14/1"
                    " ! vaapivc1dec".format(**vars(self)),
    )
    self.decode()

  @slash.parametrize(("case"), sorted(spec_r2r.keys()))
  def test_r2r(self, case):
    vars(self).update(spec_r2r[case].copy())
    vars(self).update(
      case        = case,
      gstdecoder  = "'video/x-wmv,profile=(string)advanced'"
                    ",width={width},height={height},framerate=14/1"
                    " ! vaapivc1dec".format(**vars(self)),
    )
    vars(self).setdefault("r2r", 5)
    self.decode()
