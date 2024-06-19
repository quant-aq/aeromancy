# Quick start

This guide will walk you through some of the basic Aeromancy workflows. For a
high level overview of what problems Aeromancy is trying to solve, check out our
[SciPy 2024](scipy_abstract.md) abstract.

## Creating a project

To quickly set up an Aeromancy project, we've created a
[Copier](https://copier.readthedocs.io/en/stable/) template at
[quant-aq/aeromancy-project-template](https://github.com/quant-aq/aeromancy-project-template?tab=readme-ov-file#quick-start).
Let's start by creating a new project called `aerodemo`:

1. Install [PDM](https://pdm.fming.dev) with
   [Copier](https://copier.readthedocs.io/en/stable/) support:

    ```bash
    pip install --user "pdm[copier]"
    ```

2. Set up a new Aeromancy-managed project with the template. This will create
   the project directory `aerodemo` for you:

    ```bash
    copier copy --trust "gh:quant-aq/aeromancy-project-template" aerodemo
    ```

    The template will ask a lot of questions. For the purpose of this Quick
    Start, it's fine to fill in `aerodemo` or defaults for all fields.

3. Install project dependencies:

    ```bash
    cd aerodemo
    git init
    pdm install --dev --no-self
    ```

## What's in an Aeromancy project?

Aeromancy projects contain several different components. For now, we'll start
with the three most important: (see [Tasks, Trackers, and Actions](tasks.md) for
more details on these and the other main classes)

### Actions

[`Action`][aeromancy.action.Action]s define a specific data transformation you'd
like to track with Aeromancy (e.g., training a model or performing a step in a
data processing pipeline). If you're familiar with
[Luigi](https://luigi.readthedocs.io/en/stable/) and other pipeline builders,
this may be familiar. [`Action`][aeromancy.action.Action]s roughly correspond to
a run on [Weights and Biases](https://docs.wandb.ai/quickstart) (Aeromancy will
help you create the runs on the Weights and Biases side).

In `src/aerodemo/actions.py`, we include three example
[`Action`][aeromancy.action.Action]s: `ExampleIngestAction`,`ExampleTrainAction`,
and `ExampleEvaluationAction`. Let's walk through these.

!!! note
    We'll likely be simplifying the [`Action`][aeromancy.action.Action] API in
    the near future. We hope to streamline it significantly.

#### Creating `Artifact`s with `ExampleIngestAction`

```python
class ExampleIngestAction(Action):
    """Example Aeromancy `Action` to ingest an existing dataset."""
```

[`Action`][aeromancy.action.Action]s have class attributes help you organize
your Actions and will be exposed later in experiment trackers like [Weights and
Biases](https://docs.wandb.ai/quickstart). From most general to most specific, here are the three organizational levels Weights and Biases (and thus Aeromancy) provides:

- `project_name` (defined by [`ActionBuilder`][aeromancy.action_builder.ActionBuilder])
    - `job_group`
        - `job_type`
            - individual [`Action`][aeromancy.action.Action]s

 Our example represents a typical ML flow with three
[`Action`][aeromancy.action.Action]s:

1. `job_group=model, job_type=ingest-dataset`: Store the dataset as a tracked
   artifact in Aeromancy (more on artifacts soon!)
2. `job_group=model, job_type=train-model`: Train a model from the dataset
3. `job_group=model, job_type=eval-emodel`: Evaluate a model on the dataset

```python
    job_type = "ingest-dataset"
    job_group = "model"
```

`outputs()` tells Aeromancy what artificts this Action produces. Most
[`Action`][aeromancy.action.Action]s only create a single thing (e.g., a
training action creates a model, an evaluation action could output its
predictions over the dataset) but multiple outputs are allowed. Also note that
these can be dynamically generated based on the configuration of the
[`Action`][aeromancy.action.Action].

```python
    @override
    def outputs(self) -> list[str]:
        return ["example-dataset"]
```

`run()` defines the actual logic that should be tracked (train a model,
transform a dataset, etc.). Within `run()`, we're responsible for declaring
input and output artifacts with the provided
[`Tracker`][aeromancy.tracker.Tracker]. Much of the work in this example centers
around configuring an output artifact with
[`tracker.declare_output`][aeromancy.Tracker.declare_output].

!!! question
    Why is this so complicated? Declaring an output artifact has several effects
    which Aeromancy will bind together:

    1. It creates a tracked (versioned) artifact from a set of local files.
    2. This makes the artifact usable in downstream
        [`Action`][aeromancy.action.Action] -- we'll access the files through
        Aeromancy rather than directly from disk, in fact, since it will ensure that
        we're using the correct version of it.
    3. It will store the artifact to an S3-compatible blob store, creating a
        permanent and versioned reference to the contents (well, as permanent
        as the blob store).
    4. It will create a corresponding Weights and Biases artifact which will
        be associated with the corresponding Weights and Biases run and the
        Aeromancy Artifact.

```python
    @override
    def run(self, tracker: Tracker) -> None:
        print("Hello world from ExampleIngestAction.")
```

Our dataset already exists on disk in a special directory (`data/`) which is
accessible both inside and outside the Docker container. This should generally
only be used for initial dataset ingestion -- downstream
[`Action`][aeromancy.action.Action]s should not use this path.

```python
        dataset_paths = [
            Path("data/example_train_data.txt"),
            Path("data/example_test_data.txt"),
        ]
```

We can associate arbitrary metrics with the dataset:

```python
        dataset_metadata = {
            "num_train_records": dataset_paths[0].read_text().splitlines(),
            "num_test_records": dataset_paths[1].read_text().splitlines(),
        }
```

We'll use `outputs()` from above to keep artifact names in sync.

```python
        [dataset_artifact_name] = self.outputs()
```

Now we're ready to declare `dataset_artifact_name` as an output dependency with
[`tracker.declare_output`][aeromancy.Tracker.declare_output]. We'll go over each
argument:

- `name`: This is the name of the artifact we're declaring. This name is used in
  many places:

    1. It needs to match one of the names in list of artifact names returned by
        `outputs()`, so it will be part of the name of any jobs that run this
        Action.
    2. Downstream [`Action`][aeromancy.action.Action]s will be able to refer to
       this artifact by this name.
    3. This is also the name of the corresponding Weights and Biases artifact.
- `local_filenames`: A list of files that should be included in the artifact.
- `s3_destination`: Where to store the artifact in the blob store -- this
  includes the bucket and key (a path prefix). This is purely for organization
  purposes -- naming destinations clearly could also aid with debugging but in
  general, you won't need to know or use S3 paths.
- `artifact_type`: This is purely for organization purposes and will be exposed
  in Weights and Biases. We recommend a human-readable version of the file type.
- `metadata`: This is an optional property for any extra metadata that you'd
  like to associate with the artifact (it will also be exposed in Weights and
  Biases). It can also include nested data and store a wide range of types.
- `strip_prefix`: This is the portion of the `local_filenames` paths that we
  don't want to use include in our artifact names on the blob store. In this
  case, this means we'll store `data/example_train_data.txt` as
  `dataset/bogus-example_train_data.txt` in the `example-bucket` bucket (the
  `dataset/` comes from our `s3_destination` key).

```python
        tracker.declare_output(
            name=dataset_artifact_name,
            local_filenames=dataset_paths,
            s3_destination=S3Object("example-bucket", "dataset/"),
            artifact_type="dataset",
            metadata=dataset_metadata,
            strip_prefix="data/",
        )
```

We've created our first [`Action`][aeromancy.action.Action]. Next, let's look at
`ExampleTrainAction` which will use the dataset stored by `ExampleIngestAction`.

#### Using configuration options and `Artifact`s with `ExampleTrainAction`

We'll focus on the novel parts of `ExampleTrainAction` (see the generated code
for some additional commentary). First, we'll introduce a configuration
parameter. Parameters can be anything that changes behavior or helps you
organize your experiments -- these include hyperparameters, toggling features,
or your own metadata. Let's look at `__init__` where `learning_rate` is our
example configuration parameter. Also note that we take a reference to a
`ExampleIngestAction`. This will indicate a dependency and help Aeromancy know
that it needs to run first. You might also be wondering about where
`ingest_dataset` and `learning_rate` are set -- this will happen later in our
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder].

```python
    def __init__(
        self,
        ingest_dataset: ExampleIngestAction,
        learning_rate: float,
    ):
        self.learning_rate = learning_rate
```

We need to call our superconstructor which include `ingest_dataset` as a parent
Action as well as our configuration parameter:

```python
        Action.__init__(self, parents=[ingest_dataset], learning_rate=learning_rate)
```

In our `run()` method, now we'll be able to use the artifact from our parent:

```python
    @override
    def run(self, tracker: Tracker) -> None:
        print("Hello world from ExampleTrainAction.")
```

This demonstrates `get_io()`, a helper method to simultaneously provide input
and output artifact names. Most [`Action`][aeromancy.action.Action]s include a
call to this. Note that inputs and outputs are each lists which is why we're
using brackets to unpack these. Also note that the order of the input artifact
names will follow the order of parent [`Action`][aeromancy.action.Action]s (see
`ExampleEvaluationAction` for an example of an
[`Action`][aeromancy.action.Action] with multiple parents and thus multiple
input artifacts).

```python
        [dataset_artifact_name], [model_artifact_name] = self.get_io()
```

Once we know the name of our input artifact, we need to declare it as a
dependency. This is the counterpart of
[`tracker.declare_output`][aeromancy.Tracker.declare_output] from
`ExampleIngestAction`. It will resolve the artifact to the appropriate version
and return the paths we should use to read the dataset.

```python
        dataset_paths = tracker.declare_input(dataset_artifact_name)

        train_data = dataset_paths[0].read_text()
        print(f"Training data: {train_data!r}")
```

#### Logging metrics

As we've already seen, we can associate arbitrary metadata/metrics with
artifacts as part of
[`tracker.declare_output`][aeromancy.Tracker.declare_output]. We can also log
metrics about the status of an `Action` with
[`tracker.log`][aeromancy.Tracker.log]. Returning to the `run()` method in
`ExampleTrainAction`:

```python
        # Now we pretend to train a model.
        num_iterations = 10
        # Seeding your RNG is always a good idea for better reproducibility.
        rng = random.Random(x=7)
        for step in range(num_iterations):
            # We can store information about the experiment while it's being
            # run.
            tracker.log(
                {
                    "step": step,
                    "train_error": rng.random(),
                },
            )
```

### ActionBuilder

An [`ActionBuilder`][aeromancy.action_builder.ActionBuilder]
(`src/aerodemo/action_builder.py`) is responsible for constructing a dependency
graph of [`Action`][aeromancy.action.Action]s. It will be able to receive
options from the command-line in `__init__`:

```python
    def __init__(
        self,
        learning_rate: float,
    ):
        """Create an `ActionBuilder` for aerodemo."""
        # The project name is for organizational purposes and will be the
        # project name in Weights and Biases.
        ActionBuilder.__init__(self, project_name="aerodemo")

        self.learning_rate = learning_rate
```

The main logic here happens in
[`build_actions`][aeromancy.ActionBuilder.build_actions], which constructs the
[`Action`][aeromancy.action.Action] objects we defined above. When we construct
an [`Action`][aeromancy.action.Action], we need to add it to a list using
[`self.add_action`][aeromancy.ActionBuilder.add_action]:

!!! note
    This API is likely to be simplified in the near future.

```python
    @override
    def build_actions(self) -> list[Action]:
        actions = []

        # Build each Action in sequence. Note that we use the helper method
        # add_action rather than appending to the list directly, since
        # add_action needs to do some work behind the scenes.
        ingest_action = self.add_action(actions, ExampleIngestAction(parents=[]))
        train_action = self.add_action(
            actions,
            ExampleTrainAction(
                ingest_dataset=ingest_action,
                learning_rate=self.learning_rate,
            ),
        )
        self.add_action(
            actions,
            ExampleEvaluationAction(
                ingest_dataset=ingest_action,
                train_model=train_action,
            ),
        )
        return actions
```

### AeroMain

`src/main.py`, typically referred to as **AeroMain**, is the command-line entry
point to an Aeromancy project, responsible for determining configuration
options, constructing an
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder], and launching it. By
default, Aeromancy will always look for AeroMain in `src/main.py`.

It uses [Click](https://click.palletsprojects.com/) for option parsing and
Aeromancy provides a bundle of its own options in
[`@aeromancy_click_options`][aeromancy.click_options.aeromancy_click_options].
Using [`rich.console`](https://rich.readthedocs.io/en/stable/console.html) for
console logging is optional.

```python
@click.command()
@click.option(
    "-l",
    "--learning-rate",
    metavar="FLOAT",
    default=1e-3,
    type=float,
    help="Learning rate in optimizer.",
)
# We also need to include a list of standard Aeromancy options.
@aeromancy_click_options
# Make sure to include any new options we created as arguments to aeromain.
def aeromain(
    learning_rate: float,
    **aeromancy_options,
):
    """CLI application for controlling aerodemo."""
```

Within the `aeromain()` function, we construct an
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder] (you can use more than
one if you have several similar pipelines in the same experiment), then convert
it to to an [`ActionRunner`][aeromancy.action_runner.ActionRunner] and run the
actions:

```python
    config = {"learning_rate": learning_rate}
    console.log("Config parameters from CLI:", config)

    # This builds our Action dependency graph given the configuration passed in.
    action_builder = ExampleActionBuilder(**config)
    # We create a corresponding runner to execute the dependency graph and kick
    # it off.
    action_runner = action_builder.to_runner()
    action_runner.run_actions(**aeromancy_options)
```

## Running our first experiments

Aeromancy projects all include standard scripts for running Aeromancy. The main
script is called `go` which runs AeroMain. For the Quick Start, we'll use
development mode with the `--dev` flag.

!!! info
    **Development mode** makes it easy to test and develope pipelines quickly.
    It lets you run uncommitted code outside of a Docker container and Weights
    and Biases to speed up the developer loop. It will attempt to read artifacts
    from S3 so doesn't work completely offline (unless you already have the
    artifacts cached from previous development mode runs). It's behavior is very
    close to "production" mode with the main exception that it is not
    necessarily using the same artifact versions.

### Listing available [`Action`][aeromancy.action.Action]s

Let's start by listing all the
[`Action`][aeromancy.action.Action] with `--list`:

```bash
pdm go --dev --list
```

You should see something like this:

```bash
[12:00:00] Running 'pdm run python src/main.py --list'
[12:00:01] Config parameters from CLI:
           {'learning_rate': 0.001}
[ingest-dataset] example-dataset
[train-model] example-model
[eval-model] example-model-predictions
```

We can see the results of our `console.log` statement with the default value for
 the learning rate parameter. This is followed by a list of all
[`Action`][aeromancy.action.Action]s our
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder] built. The `job_type`
is shown in brackets, followed by a list of output artifacts.

### Running the pipeline

Assuming we're happy with the [`Action`][aeromancy.action.Action]s, we can run
them all by omitting `--list`:

```bash
pdm go --dev
```

You should see it run each [`Action`][aeromancy.action.Action] in sequence.
Don't worry if it's overwhelming at first. Because we're running in development
mode, we're using a [fake tracker][aeromancy.fake_tracker.FakeTracker] instead
of the production Weights and Biases tracker, so you'll see a lot of messages
from it about what would happen if we were running in production mode.

### Job selection

Sometimes (in our experience, often) we don't want to run the entire pipeline.
To run just some of the jobs, pass the `--only` flag. Aeromancy will then only
run jobs with a name that includes that substring. You can pass it a
comma-separated list. Note that names include the `job_type` as well.

!!! example

    - If you pass `--only train`, it will just run `ExampleTrainAction`

    - If you pass `--only model`, it will run `ExampleTrainAction` then
    `ExampleEvaluationAction` (since the latter depends on the former)

    - If you pass `--only dataset,train`, it will run  `ExampleIngestAction` then
    `ExampleTrainAction`

## What's next?

We've gone through all the main components you'll need to define to run
experiments in Aeromancy and how to run them in development mode. Next up, you
might want to:

- [Configure](setup.md) Aeromancy to work with Weights and Biases and
  S3-compatible blob stores (production mode)
- (To be documented) Developing and Debugging (`bailout`, `--debug`, common
  pitfalls, `aeroset`, `aeroview`, `rerun` commands)
- [Customizing](customizing.md) your Aeromancy project
- (To be documented) Best practices and FAQ
- (To be documented) Debugging Aeromancy itself (for Aeromancy developers)
