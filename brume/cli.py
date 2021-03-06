"""
Brume CLI module.
"""

import json
from glob import glob
from os import path

import click
from yaml import dump

import brume.config
from brume import VERSION
from brume.assets import send_assets
from brume.boto_client import bucket_exists
from brume.checker import check_templates
from brume.stack import Stack
from brume.template import Template


class Context(object):
    """
    Context object to hold the configuration.
    """

    def __init__(self):
        self.config = dict()
        self.stack = None
        self.debug = False
        self.region = None


pass_ctx = click.make_pass_decorator(Context, ensure=True)


def config_callback(ctx, _, value):
    """
    Initialize context object
    """
    ctx = ctx.ensure_object(Context)
    brume.config.configuration_file = value
    ctx.config = brume.config.Config.load()
    if ctx.region is None:
        ctx.region = ctx.config['region']
    ctx.stack = Stack(ctx.region, ctx.config['stack'])
    return value


@click.group()
@click.version_option(VERSION, '-v', '--version')
@click.help_option('-h', '--help')
@click.option('-c', '--config', expose_value=False, default=brume.config.DEFAULT_BRUME_CONFIG,
              help='Configuration file (defaults to {}).'.format(brume.config.DEFAULT_BRUME_CONFIG),
              callback=config_callback)
def cli():
    """Set global cli option"""
    pass


@cli.command()
@pass_ctx
def config(ctx):
    """Print the current stack configuration."""
    click.echo(dump(ctx.config, default_flow_style=False))


@cli.command()
@pass_ctx
def create(ctx):
    """Create a new CloudFormation stack."""
    validate_and_upload(ctx.region, ctx.config)
    ctx.stack.create()


@cli.command()
@pass_ctx
def update(ctx):
    """Update an existing CloudFormation stack."""
    validate_and_upload(ctx.region, ctx.config)
    ctx.stack.update()


@cli.command()
@pass_ctx
def deploy(ctx):
    """Create or update a CloudFormation stack."""
    validate_and_upload(ctx.region, ctx.config)
    ctx.stack.create_or_update()
    ctx.stack.outputs()


@cli.command()
@pass_ctx
def delete(ctx):
    """Delete the CloudFormation stack."""
    ctx.stack.delete()


@cli.command()
@pass_ctx
def status(ctx):
    """Get the status of a CloudFormation stack."""
    ctx.stack.status()


@cli.command()
@pass_ctx
@click.option('--flat', is_flag=True, help='Flat format (only for the text output format)')
@click.option('output_format', '-f', '--format', type=click.Choice(['text', 'json', 'yaml']),
              default='text', help='Output format (text/json/yaml)')
def outputs(ctx, output_format, flat=False):
    """Get the full list of outputs of a CloudFormation stack."""
    stack_outputs = ctx.stack.outputs()
    if output_format == 'text':
        if flat:
            for _, outputs in stack_outputs.items():
                for output_name, output_value in outputs.items():
                    click.echo('{} = {}'.format(output_name, output_value))
        else:
            for stack_name, outputs in stack_outputs.items():
                if not outputs:
                    continue
                if ':stack/' in stack_name:
                    stack_name = stack_name.partition(':stack/')[2].split('/')[0]
                click.echo(stack_name)
                for output_name, output_value in outputs.items():
                    click.echo('\t{} = {}'.format(output_name, output_value))
                click.echo()
    elif output_format == 'yaml':
        click.echo(dump(stack_outputs, default_flow_style=False))
    elif output_format == 'json':
        click.echo(json.dumps(stack_outputs, indent=True))


@cli.command()
@pass_ctx
@click.option('--flat', is_flag=True, help='Flat format (only for the text output format)')
@click.option('output_format', '-f', '--format', type=click.Choice(['text', 'json', 'yaml']),
              default='text', help='Output format (text/json/yaml)')
def parameters(ctx, output_format, flat=False):
    """Get the full list of parameters of a CloudFormation stack."""
    stack_params = ctx.stack.params()
    if output_format == 'text':
        if flat:
            for _, stack_params in stack_params.items():
                for param_name, param_value in stack_params.items():
                    click.echo('{} = {}'.format(param_name, param_value))
        else:
            for stack_name, stack_parameters in stack_params.items():
                if not stack_parameters:
                    continue
                if ':stack/' in stack_name:
                    stack_name = stack_name.partition(':stack/')[2].split('/')[0]
                click.echo(stack_name)
                for param_name, param_value in stack_parameters.items():
                    click.echo('\t{} = {}'.format(param_name, param_value))
                click.echo()
    elif output_format == 'yaml':
        click.echo(dump(stack_params, default_flow_style=False))
    elif output_format == 'json':
        click.echo(json.dumps(stack_params, indent=True))


@cli.command()
@pass_ctx
def validate(ctx):
    """Validate CloudFormation templates."""
    error = False
    for t in collect_templates(ctx.config):
        valid = t.validate()
        if not valid:
            error = True
    if error:
        exit(1)


@cli.command()
@pass_ctx
def upload(ctx):
    """Upload CloudFormation templates and assets to S3."""
    process_assets(ctx.region, ctx.config)
    return [t.upload() for t in collect_templates(ctx.config)]


@cli.command()
@pass_ctx
def check(ctx):
    """Check CloudFormation templates."""
    check_templates(ctx.config['stack']['template_body'])


def process_assets(region, conf):
    """Upload project assets to S3."""
    if 'assets' not in conf:
        return
    assets_config = conf['assets']
    local_path = assets_config['local_path']
    s3_bucket = assets_config['s3_bucket']
    s3_path = assets_config['s3_path']
    if bucket_exists(region, s3_bucket):
        click.echo('Processing assets from {} to s3://{}/{}'.format(local_path, s3_bucket, s3_path))
        send_assets(region, local_path, s3_bucket, s3_path)
    else:
        click.echo('Bucket does not exist {}'.format(s3_bucket))


def collect_templates(conf):
    """
    Convert every template into a brume.Template.

    The type of the templates is determined based on the `template_body`
    property of the configuration file.
    """
    _file, ext = path.splitext(conf['stack']['template_body'])
    template_paths = glob(path.join(conf['templates'].get('local_path', ''), '*' + ext))
    return [Template(t, conf['templates']) for t in template_paths]


def validate_and_upload(region, conf):
    """Validate and upload CloudFormation templates to S3."""
    templates = collect_templates(conf)
    error = False
    for t in templates:
        if not t.validate():
            error = True
    if error:
        exit(1)
    for t in templates:
        t.upload()
    process_assets(region, conf)


if __name__ == '__main__':
    cli()
