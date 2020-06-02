import json
import numpy as np
import pandas as pd
from collections import defaultdict
from pathlib import Path
from tempfile import mkdtemp
from bids.analysis import Analysis as BIDSAnalysis
from bids.layout import BIDSLayout
from copy import deepcopy
from grabbit.extensions.writable import build_path

PATHS = ['sub-{subject}_[ses-{session}_]task-{task}_[acq-{acquisition}_]'
         '[run-{run}_]events.tsv']


def writeout_events(analysis, pes, outdir, run_ids=None):
    """ Writeout predictor_events into BIDS event files """
    analysis_runs = analysis.get('runs', [])
    if run_ids is not None:
        analysis_runs = [r for r in analysis_runs if r in run_ids]

    desc = {
        'Name': analysis['hash_id'],
        'BIDSVersion': '1.1.1',
        'PipelineDescription': {'Name': 'Neuroscout Events'}
        }

    desc_path = (outdir / 'dataset_description.json')
    paths = [(str(desc_path), 'dataset_description.json')]
    json.dump(desc, desc_path.open('w'))

    outdir = outdir / "func"
    outdir.mkdir(exist_ok=True)

    # Load events and rename columns to human-readable
    pes = pd.DataFrame(pes)
    predictor_names = {p['id']: p['name'] for p in analysis['predictors']}
    pes.predictor_id = pes.predictor_id.map(predictor_names)

    # Write out event files
    for run in analysis_runs:
        # Write out event files for each run_id
        run_events = pes[pes.run_id == run['id']].drop('run_id', axis=1)
        entities = _get_entities(run)
        entities['task'] = analysis['task_name']

        out_cols = {}
        if run_events.empty is False:
            for name, df in run_events.groupby('predictor_id'):
                df_col = df.groupby(['onset', 'duration'])['value'].max()
                df_col = df_col.reset_index().rename(
                    columns={'value': name})
                out_cols[name] = df_col

        # For any columns that don't have events, output n/a file
        for name in set(predictor_names.values()) - out_cols.keys():
            df_col = pd.DataFrame([[0, 0, 'n/a']],
                                  columns=['onset', 'duration', name])
            out_cols[name] = df_col

        # Write out files
        for name, df_col in out_cols.items():
            # Write out BIDS path
            fname = outdir / name / build_path(
                entities, path_patterns=PATHS)
            fname.parent.mkdir(exist_ok=True)
            paths.append(
                (str(fname), 'events/{}/{}'.format(name, fname.name)))
            df_col.to_csv(fname, sep='\t', index=False)

    return paths


def build_analysis(analysis, predictor_events, bids_dir,
                   run_ids=None, build=True):
    """ Write out and build analysis object """
    tmp_dir = Path(mkdtemp())

    # Get set of entities across analysis
    entities = [{}]
    if run_ids is not None:
        # Get entities of runs, and add to kwargs
        for rid in run_ids:
            for run in analysis['runs']:
                if rid == run['id']:
                    entities.append(_get_entities(run))
                    break

    entities = _merge_dictionaries(*entities)
    entities['scan_length'] = max([r['duration'] for r in analysis['runs']])
    entities['task'] = analysis['task_name']

    # Write out all events
    paths = writeout_events(analysis, predictor_events, tmp_dir, run_ids)

    if build is False:
        bids_analysis = None
    else:
        # Load events and try applying transformations
        bids_layout = BIDSLayout(bids_dir, derivatives=str(tmp_dir),
                                 validate=False)
        bids_analysis = BIDSAnalysis(
            bids_layout, deepcopy(analysis.get('model')))
        bids_analysis.setup(**entities)

    return tmp_dir, paths, bids_analysis


def _get_entities(run):
    """ Get BIDS-entities from run object """
    valid = ['number', 'session', 'subject', 'acquisition']
    entities = {
        r: v
        for r, v in run.items()
        if r in valid and v is not None
        }

    if 'number' in entities:
        entities['run'] = entities.pop('number')
    return entities


def _merge_dictionaries(*arg):
    """ Set merge dictionaries """
    dd = defaultdict(set)

    for d in arg:  # you can list as many input dicts as you want here
        for key, value in d.items():
            dd[key].add(value)
    return dict(((k, list(v)) if len(v) > 1 else (k, list(v)[0])
                 for k, v in dd.items()))


def impute_confounds(dense):
    """ Impute first TR for confounds that may have n/as """
    for imputable in ('framewise_displacement', 'std_dvars', 'dvars'):
        if imputable in dense.columns:
            vals = dense[imputable].values
            if not np.isnan(vals[0]):
                continue

            # Impute the mean non-zero, non-NaN value
            dense[imputable][0] = np.nanmean(vals[vals != 0])
    return dense
