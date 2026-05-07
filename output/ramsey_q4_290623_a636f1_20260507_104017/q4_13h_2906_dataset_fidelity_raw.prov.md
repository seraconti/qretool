graph LR
  A["290623_6D2S_qubit4.pickle\n61331e"]
  A --> B["load_df(dataset=Dataset(path=PosixPath('FOR ZENODO/Main/Fig 2/qubit4.pickle'), schema=None, qubit=None, device=None, duration_h=None, extra={}))"]
  B --> C["lookup_prior(fields=['frequency', 'Rabi_frequency'], aliases={'frequency': 'qubit_frequency'})"]
  C --> D["filter"]
  D --> E["final_filter_stage"]
  E --> F["fidelity_raw"]
  F --> G["q4_13h_2906_dataset_fidelity_raw\ngit:nogit"]
