graph LR
  A["030723_2x2_qubit2.pickle\nb4f0e3"]
  A --> B["filter"]
  B --> C["final_filter_stage"]
  C --> D["interpolate"]
  D --> E["allan(fractional=False, carrier_col='frequency')"]
  E --> F["AllanPlot\ngit:nogit"]
