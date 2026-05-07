graph LR
  A["120423_6D2S_qubit1.pickle\nbe9f3d"]
  A --> B["load_df(dataset=Dataset(path=PosixPath('FOR ZENODO/Main/Fig 2/qubit1.pickle'), schema=None, qubit=None, device=None, duration_h=None, extra={}))"]
  B --> C["lookup_prior(fields=['frequency', 'Rabi_frequency'], aliases={'frequency': 'qubit_frequency'})"]
  C --> D["filter"]
  D --> E["final_filter_stage"]
  E --> F["interpolate"]
  F --> G["allan(fractional=True, carrier_col='qubit_frequency')"]
  G --> H["AllanPlot\ngit:nogit"]
