graph LR
  A["070723_6D2S_qubit6.pickle\n71a6a7"]
  A --> B["load_df(dataset=Dataset(path=PosixPath('FOR ZENODO/Main/Fig 2/qubit6.pickle'), schema=None, qubit=None, device=None, duration_h=None, extra={}))"]
  B --> C["lookup_prior(fields=['frequency', 'Rabi_frequency'], aliases={'frequency': 'qubit_frequency'})"]
  C --> D["filter"]
  D --> E["final_filter_stage"]
  E --> F["tlf"]
  F --> G["TLFPlot\ngit:nogit"]
