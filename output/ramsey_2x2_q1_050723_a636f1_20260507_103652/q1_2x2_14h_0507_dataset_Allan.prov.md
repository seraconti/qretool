graph LR
  A["050723_2x2_qubit1.pickle\nd6a3f6"]
  A --> B["filter"]
  B --> C["final_filter_stage"]
  C --> D["interpolate"]
  D --> E["allan(fractional=False, carrier_col='frequency')"]
  E --> F["AllanPlot\ngit:nogit"]
