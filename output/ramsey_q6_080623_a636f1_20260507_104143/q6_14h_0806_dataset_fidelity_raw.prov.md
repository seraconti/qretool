graph LR
  A["080623_6D2S_qubit6.pickle\na64c12"]
  A --> B["load_df(dataset=Dataset(path=PosixPath('FOR ZENODO/Main/Fig 2/qubit6.pickle'), schema=None, qubit=None, device=None, duration_h=None, extra={}))"]
  B --> C["lookup_prior(fields=['frequency', 'Rabi_frequency'], aliases={'frequency': 'qubit_frequency'})"]
  C --> D["filter"]
  D --> E["final_filter_stage"]
  E --> F["fidelity_raw"]
  F --> G["q6_14h_0806_dataset_fidelity_raw\ngit:nogit"]
