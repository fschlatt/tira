from pyterrier.transformer import Transformer
import json
import pandas as pd


class TiraRerankingTransformer(Transformer):
    """
    A Transformer that loads runs from TIRA that reranked some existing run.
    """

    def __init__(self, approach, tira_client, **kwargs):
        self.task, self.team, self.software = approach.split('/')
        self.tira_client = tira_client

    def transform(self, topics):
        import numpy as np
        assert "qid" in topics.columns
        if 'tira_task' not in topics.columns or 'tira_dataset' not in topics.columns or 'tira_first_stage_run_id' not in topics.columns:
            raise ValueError('This run needs to know the tira metadata: tira_task, tira_dataset, and tira_first_stage_run_id needs to be in the columns of the dataframe')

        tira_configurations = [json.loads(i) for i in topics[['tira_task', 'tira_dataset', 'tira_first_stage_run_id']].apply(lambda i: json.dumps(i.to_dict()), axis=1).unique()]
        df = []
        for tira_configuration in tira_configurations:
            df += [self.tira_client.download_run(tira_configuration['tira_task'], tira_configuration['tira_dataset'], self.software, self.team, tira_configuration['tira_first_stage_run_id'])]
        df = pd.concat(df)

        common_columns = np.intersect1d(topics.columns, df.columns)

        # we drop columns in topics that exist in the df
        keeping = topics.columns
        drop_columns = common_columns[common_columns != "qid"]
        if len(drop_columns) > 0:
            keeping = topics.columns[~ topics.columns.isin(drop_columns)]

        return topics[keeping].merge(df, on="qid")
