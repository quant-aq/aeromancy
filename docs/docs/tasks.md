# Tasks, Trackers, and Actions: Your guide to Aeromancy's Terminological Soup

<!-- TODO: These look best in mkdocs HTML. Maybe we can find a better way of
doing the cross-references. -->

The terminology can get confusing here, as there are several similarly named but
functionally different pieces. The following diagram summarizes the key
relationships:

``` mermaid
graph LR
  ActionBuilder -->|Convertible to| ActionRunner
  ActionBuilder -->|Builds| Action
  Action -->|Instantiates| Tracker
  WandbTracker -->|Subclasses| Tracker
  FakeTracker -->|Subclasses| Tracker
  Action -->|Convertible to| Task[pydoit.Task]
  ActionRunner -->|Executes| Task
```

## [`Tracker`][aeromancy.tracker.Tracker]

Creates an environment for to track code for reproducible ML/data science/data
pipelines/etc. For example,
[`WandbTracker`][aeromancy.wandb_tracker.WandbTracker] (a subclass) integrates
with Weights and Biases (W&B) for ML experiment tracking and S3 for external
artifact storage. This class doesn't know anything task-specific, dependencies
between tasks, or how to actually execute the code.

## [`Action`][aeromancy.action.Action]

A single task-specific node in an execution graph. Each node knows its inputs
(other [`Action`][aeromancy.action.Action]s it depends on and the results of
their computation) and outputs as well as the actual code to run the action. We
wrap the execution of an [`Action`][aeromancy.action.Action] in an Aeromancy
[`Tracker`][aeromancy.tracker.Tracker] when run (potentially a
[`FakeTracker`][aeromancy.fake_tracker.FakeTracker] for development work).
[`Action`][aeromancy.action.Action]s know a little about W&B artifact names
since they need to declare and look these up.
[`Action`][aeromancy.action.Action]s are agnostic about how/where they actually
gets executed -- that's up to a task runner which we can swap out as needed (see
[`ActionRunner`][aeromancy.action_runner.ActionRunner]).

## [`ActionBuilder`][aeromancy.action_builder.ActionBuilder]

A factory class that constructs [`Action`][aeromancy.action.Action]s with
specified dependencies for a given configuration.

## [`ActionRunner`][aeromancy.action_runner.ActionRunner]

Uses [`pydoit`](https://pydoit.org/) to execute
[`Action`][aeromancy.action.Action]s in an
[`ActionBuilder`][aeromancy.action_builder.ActionBuilder] (according to
dependencies it laid out). This includes logic to convert
[`Action`][aeromancy.action.Action]s to pydoit
[`Task`](https://pydoit.org/tasks.html)s.

## [`Task`](https://pydoit.org/tasks.html) ([pydoit](https://pydoit.org/))

A single executable task with dependencies and metadata in
[`pydoit`](https://pydoit.org/)'s framework. All logic for working with these
lives in the [`aeromancy.action_runner`][aeromancy.action_runner] module.
