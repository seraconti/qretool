graph LR
  A["300623_2x2_qubit3.pickle\nafcb55"]
  A --> B["filter"]
  B --> C["final_filter_stage"]
  C --> D["interpolate"]
  D --> E["allan(fractional=False, carrier_col='frequency')"]
  E --> F["AllanPlot\ngit:nogit"]
