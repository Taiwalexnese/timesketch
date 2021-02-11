# Copyright 2021 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Commands for explore and search."""

import json

import click
from tabulate import tabulate

from timesketch_api_client import search


def format_output(search_obj, output_format, show_headers):
    """Format search result output.

    Args:
        search_obj: API Search object.
        output_format: The format to use.
        show_headers: Boolean indicating if header row should be displayed.

    Returns:
        Search results in the requested output format.
    """
    dataframe = search_obj.to_pandas()

    # Label is being set regardless of return_fields. Remove if it is not in
    # the list of requested fields.
    if 'label' not in search_obj.return_fields:
        dataframe = dataframe.drop(columns=['label'])

    result = None
    if output_format == 'text':
        result = dataframe.to_string(index=False, header=show_headers)
    elif output_format == 'csv':
        result = dataframe.to_csv(index=False, header=show_headers)
    elif output_format == 'tabular':
        if show_headers:
            result = tabulate(
                dataframe, headers='keys', tablefmt='psql', showindex=False)
        else:
            result = tabulate(dataframe, tablefmt='psql', showindex=False)

    return result


def describe_query(search_obj):
    """Print details of a search query nd filter.

    Args:
        search_obj: API Search object.
    """
    click.echo('Query string: {}'.format(search_obj.query_string))
    click.echo('Return fields: {}'.format(search_obj.return_fields))
    click.echo('Filter: {}'.format(
        json.dumps(search_obj.query_filter, indent=2)))


@click.command('search')
@click.option(
    '--query', '-q', default='*',
    help='Search query in Elasticsearch query string format')
@click.option(
    '--time', 'times', multiple=True,
    help='Datetime filter (e.g. 2020-01-01T12:00)')
@click.option(
    '--time-range', 'time_ranges', multiple=True, nargs=2,
    help='Datetime range filter (e.g: 2020-01-01 2020-02-01)')
@click.option(
    '--label', 'labels', multiple=True,
    help='Filter events with label')
@click.option(
    '--header/--no-header', default=True,
    help='Toggle header information (default is to show)')
@click.option(
    '--output-format', 'output',
    help='Set output format (overrides global setting)')
@click.option(
    '--return-fields', 'return_fields', default='',
    help='What event fields to show')
@click.option(
    '--order', default='asc',
    help='Order the output (asc/desc) based on the time field')
@click.option(
    '--limit', type=int, default=40,
    help='Limit amount of events to show (default: 40)')
@click.option(
    '--saved-search', type=int, help='Query and filter from saved search')
@click.option(
    '--describe', is_flag=True, default=False,
    help='Show the query and filter then exit')
@click.pass_context
# pylint: disable=too-many-arguments
def search_group(ctx, query, times, time_ranges, labels, header, output,
                 return_fields, order, limit, saved_search, describe):
    """Search and explore."""
    sketch = ctx.obj.sketch
    output_format = ctx.obj.output_format
    search_obj = search.Search(sketch=sketch)

    if output:
        output_format = output

    new_line = True
    if output_format == 'csv':
        new_line = False

    # Construct query from saved search and return early.
    if saved_search:
        search_obj.from_saved(saved_search)
        if describe:
            describe_query(search_obj)
            return
        click.echo(format_output(
            search_obj, output_format, header), nl=new_line)
        return

    # Construct the query from flags.
    # TODO (berggren): Add support for query DSL.
    search_obj.query_string = query
    search_obj.return_fields = return_fields
    search_obj.max_entries = limit

    if order == 'asc':
        search_obj.order_ascending()
    elif order == 'desc':
        search_obj.order_descending()

    # TODO: Add term chips.
    if time_ranges:
        for time_range in time_ranges:
            range_chip = search.DateRangeChip()
            range_chip.start_time = time_range[0]
            range_chip.end_time = time_range[1]
            search_obj.add_chip(range_chip)

    # TODO (berggren): This should support dates like 2021-02-12 and then
    # convert to ISO format.
    if times:
        for time in times:
            range_chip = search.DateRangeChip()
            range_chip.start_time = time
            range_chip.end_time = time
            search_obj.add_chip(range_chip)

    if labels:
        for label in labels:
            label_chip = search.LabelChip()
            if label == 'star':
                label_chip.use_star_label()
            elif label == 'comment':
                label_chip.use_comment_label()
            else:
                label_chip.label = label
            search_obj.add_chip(label_chip)

    if describe:
        describe_query(search_obj)
        return

    click.echo(format_output(search_obj, output_format, header), nl=new_line)


@click.group('saved-searches')
def saved_searches_group():
    """Managed saved searches."""


@saved_searches_group.command('list')
@click.pass_context
def list_saved_searches(ctx):
    """List saved searches in the sketch.

    Args:
        ctx: Click CLI context object.
    """
    sketch = ctx.obj.sketch
    for saved_search in sketch.list_views():
        click.echo(f'{saved_search.id} {saved_search.name}')


@saved_searches_group.command('describe')
@click.argument('search_id', type=int, required=False)
@click.pass_context
def describe_saved_search(ctx, search_id):
    """Show details for a view.

    Args:
        ctx: Click CLI context object.
        search_id: View ID from argument.
    """
    sketch = ctx.obj.sketch
    # TODO (berggren): Add support for view_name.
    saved_search = sketch.get_saved_search(view_id=search_id)
    if not saved_search:
        click.echo('No such view')
        return
    click.echo('query_string: {}'.format(saved_search.query_string))
    click.echo('query_filter: {}'.format(
        json.dumps(saved_search.query_filter, indent=2)))