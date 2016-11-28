#!/usr/bin/env python

import click
import yaml
import brume

from glob import glob

conf = brume.Config.load('brume.yml')
s3_config = conf['templates']
cf_config = conf['stack']


def collect_templates():
    return [brume.Template(t) for t in glob('*.cform')]


@click.command()
def config():
    """Print the current stack confguration."""
    print(yaml.dump(conf))


@click.command()
def create():
    """Create a new CloudFormation stack."""
    stack = brume.Stack(cf_config)
    stack.create()
    stack.tail()


@click.command()
def update():
    """Update an existing CloudFormation stack."""
    stack = brume.Stack(cf_config)
    stack.update()
    stack.tail()


@click.command()
def deploy():
    """Create or update a CloudFormation stack."""
    stack = brume.Stack(cf_config)
    stack.create_or_update()
    stack.tail()


@click.command()
def delete():
    """Delete a CloudFormation stack."""
    stack = brume.Stack(cf_config)
    stack.delete()
    stack.tail()


@click.command()
def validate():
    """Validate CloudFormation templates."""
    templates = collect_templates()
    return map(lambda t: t.validate(), templates)


@click.command()
def events():
    """Tail the events of the stack."""
    brume.Stack(cf_config).tail()


@click.command()
@click.option('--bucket', required=True, help='Name of the bucket')
@click.option('--prefix', required=True, help='Prefix to the file name')
def upload(templates, bucket, path_prefix):
    """Upload CloudFormation templates to S3."""
    [t.upload(bucket, path_prefix) for t in templates]
    return templates


@click.group()
def cli():
    pass

cli.add_command(create)
cli.add_command(update)
cli.add_command(deploy)
cli.add_command(upload)
cli.add_command(delete)
cli.add_command(validate)
cli.add_command(config)
cli.add_command(events)

if __name__ == '__main__':
    cli()
