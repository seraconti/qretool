graph LR
  A["290623_6D2S_qubit6.pickle\ndf97c9"]
  A --> B["load_df(dataset=Dataset(path=PosixPath('FOR ZENODO/Main/Fig 2/qubit6.pickle'), schema=None, qubit=None, device=None, duration_h=None, extra={}))"]
  B --> C["lookup_prior(fields=['frequency', 'Rabi_frequency'], aliases={'frequency': 'qubit_frequency'})"]
  C --> D["filter"]
  D --> E["final_filter_stage"]
  E --> F["interpolate"]
  F --> G["allan(fractional=True, carrier_col='qubit_frequency')"]
  G --> H["AllanPlot\ngit:nogit"]
