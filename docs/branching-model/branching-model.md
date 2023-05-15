# Branching Model

This page describes the branching model used for the Commander Spellbook Backend project, based on Git.

## Trunk based development

It is suggested to follow and contribute to the project using the trunk based development model.
Basically, every commit is done on `master`.
This is the simplest model, and it is suggested to use it for small projects.

If a new feature is being developed, a new branch can be created from master, but it is not required.
The feature branch name should be prefixed with `feature/`.
When the feature is ready, it can be merged into master, and the feature branch can be deleted.

## Semantic versioning and annotated tags

Versioning is done using [semantic versioning](https://semver.org/).
Release branches are not allowed.
Instead, a new version is created by tagging the commit on master, using a [git annotated tag](https://git-scm.com/book/en/v2/Git-Basics-Tagging#_annotated_tags).

When a new version tag is added, it must represent a higher version than any previous tag.
The version must be updated according to semantic versioning rules.
The tag name must be prefixed with `v`, and it must be followed by the version number.
For example, `v1.0.0` is a valid tag name.

### Continuous delivery

Whenever a new annotated tag is pushed to the remote repository, the continuous delivery pipeline will be triggered.

### Helper scripts

You can download a MIT Licensed semantic version helper script from [here](https://github.com/francescodente/git-release) and put it in your path.
If you do so, you can use the following commands to create a new version tag:
    
```bash
git release major
git release minor
git release patch
```

Each of these commands will increment the corresponding part of the version number, and create a new annotated tag.
In addition to that, it will also sync the current branch with the remote repository, and push the new tag afterwards.
