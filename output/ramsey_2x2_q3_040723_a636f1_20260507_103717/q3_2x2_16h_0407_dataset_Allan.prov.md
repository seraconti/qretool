graph LR
  A["040723_2x2_qubit3.pickle\n75cbc2"]
  A --> B["filter"]
  B --> C["final_filter_stage"]
  C --> D["interpolate"]
  D --> E["allan(fractional=False, carrier_col='frequency')"]
  E --> F["AllanPlot\ngit:nogit"]
