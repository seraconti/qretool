graph LR
  A["100423_6D2S_qubit1.pickle\n2ad845"]
  A --> B["load_df(dataset=Dataset(path=PosixPath('FOR ZENODO/Main/Fig 2/qubit1.pickle'), schema=None, qubit=None, device=None, duration_h=None, extra={}))"]
  B --> C["lookup_prior(fields=['frequency', 'Rabi_frequency'], aliases={'frequency': 'qubit_frequency'})"]
  C --> D["filter"]
  D --> E["final_filter_stage"]
  E --> F["fidelity_raw"]
  F --> G["q1_13h_1004_dataset_fidelity_raw\ngit:nogit"]
