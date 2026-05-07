graph LR
  A["070723_2x2_qubit1.pickle\n4dddbe"]
  A --> B["filter"]
  B --> C["final_filter_stage"]
  C --> D["interpolate"]
  D --> E["allan(fractional=False, carrier_col='frequency')"]
  E --> F["AllanPlot\ngit:nogit"]
